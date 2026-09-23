// This plugin is copied into an isolated OpenCode test profile for grey-box runs.
import * as fs from "node:fs";

const enabled = process.env.ATS_OC_HOOK_CASE_LEVEL === "grey_box";
const path = process.env.ATS_OC_HOOK_FILE;
const runId = process.env.ATS_OC_HOOK_RUN_ID;
const turnId = process.env.ATS_OC_HOOK_TURN_ID;
const maxBytes = 1024 * 1024;
const maxEvents = 4096;
const markerReserve = 512;
let overflow = false;
let count;

function safeId(value) {
  return typeof value === "string" && value.length > 0 && value.length <= 128 &&
    /^[A-Za-z0-9_.:-]+$/.test(value) ? value : null;
}

function safeName(value) {
  return typeof value === "string" && value.length > 0 && value.length <= 128 &&
    /^[A-Za-z0-9_.:/-]+$/.test(value) ? value : null;
}

function configured() {
  return enabled && typeof path === "string" && path.length > 0 &&
    safeId(runId) !== null;
}

function writeLine(event) {
  // The evaluator creates this regular file ahead of time, outside the workspace.
  if (!configured()) return;
  const flags = fs.constants.O_WRONLY | fs.constants.O_APPEND | (fs.constants.O_NOFOLLOW ?? 0);
  const fd = fs.openSync(path, flags);
  try {
    if (!fs.fstatSync(fd).isFile()) throw new Error("OpenCode evidence target is not a regular file");
    fs.writeSync(fd, JSON.stringify(event) + "\n", null, "utf8");
  } finally {
    fs.closeSync(fd);
  }
}

function emit(kind, input, details = {}) {
  if (!configured() || overflow) return;
  // Count persisted lines because opencode run creates a fresh process each turn.
  if (count === undefined) {
    const flags = fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0);
    const fd = fs.openSync(path, flags);
    let source;
    try {
      if (!fs.fstatSync(fd).isFile()) throw new Error("OpenCode evidence target is not a regular file");
      source = fs.readFileSync(fd, "utf8");
    } finally {
      fs.closeSync(fd);
    }
    if (Buffer.byteLength(source, "utf8") > maxBytes) throw new Error("OpenCode evidence file exceeds limit");
    count = source ? source.split("\n").length - 1 : 0;
    if (source.includes('"kind":"collector_overflow"')) {
      overflow = true;
      return;
    }
  }
  const event = {
    schema_version: 1,
    run_id: runId,
    session_id: safeId(input?.sessionID),
    turn_id: safeId(turnId) || (kind === "chat.params" ? safeId(input?.message?.id) : null),
    kind,
    observed_at: new Date().toISOString(),
    ...details,
  };
  const currentBytes = fs.statSync(path).size;
  const lineBytes = Buffer.byteLength(JSON.stringify(event) + "\n", "utf8");
  if (count >= maxEvents - 1 || currentBytes + lineBytes > maxBytes - markerReserve) {
    writeLine({
      schema_version: 1,
      run_id: runId,
      kind: "collector_overflow",
      observed_at: new Date().toISOString(),
    });
    overflow = true;
    return;
  }
  writeLine(event);
  count += 1;
}

export const AtsGreyBoxEvidence = async () => {
  if (!configured()) return {};
  return {
    "chat.headers": async (input, output) => {
      // One-shot grey-box subprocesses carry one evaluator-owned turn nonce.
      // The agent label distinguishes primary calls from title generation.
      // Both values describe local evaluator observations, not provider identity.
      const selectedTurn = safeId(turnId);
      const agent = safeId(input?.agent?.name) || safeId(input?.agent);
      if (!selectedTurn || !safeId(input?.sessionID) || !output?.headers ||
          typeof output.headers !== "object" || Array.isArray(output.headers) || !agent) return;
      for (const [name, value] of [["x-turn-id", selectedTurn], ["x-ats-oc-agent", agent]]) {
        const existing = Object.entries(output.headers).filter(([key]) => key.toLowerCase() === name);
        if (existing.length > 1 || existing.some(([, current]) => current !== value)) return;
      }
      if (!Object.keys(output.headers).some((key) => key.toLowerCase() === "x-turn-id"))
        output.headers["x-turn-id"] = selectedTurn;
      if (!Object.keys(output.headers).some((key) => key.toLowerCase() === "x-ats-oc-agent"))
        output.headers["x-ats-oc-agent"] = agent;
    },
    "chat.params": async (input, output) => {
      const model = input?.model;
      emit("chat.params", input, {
        user_message_id: safeId(input?.message?.id),
        model_id: safeName(model?.id) || safeName(model?.modelID),
        temperature_set: typeof output?.temperature === "number",
        top_p_set: typeof output?.topP === "number",
      });
    },
    "tool.execute.before": async (input) => {
      emit("tool.execute.before", input, {
        tool_name: safeName(input?.tool),
        tool_call_id: safeId(input?.callID),
      });
    },
    "tool.execute.after": async (input) => {
      emit("tool.execute.after", input, {
        tool_name: safeName(input?.tool),
        tool_call_id: safeId(input?.callID),
      });
    },
  };
};
