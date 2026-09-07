"""Exercise the CLI-to-MCP wiring locally without an Agent or model service."""

import argparse
import json
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-config", required=True)
    parser.add_argument("--session-id")
    parser.add_argument("--resume")
    options, _ = parser.parse_known_args()
    server = json.loads(options.mcp_config)["mcpServers"]["ats_mock"]
    request = json.loads(sys.stdin.readline())
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "offline-protocol-probe", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": request},
    ]
    completed = subprocess.run([server["command"], *server["args"]],
        input="".join(json.dumps(message) + "\n" for message in messages),
        text=True, encoding="utf-8", capture_output=True, timeout=10, check=True)
    reply = [json.loads(line) for line in completed.stdout.splitlines()][-1]
    print(json.dumps({"type": "result", "subtype": "success", "is_error": "error" in reply,
                      "result": json.dumps(reply), "session_id": options.resume or options.session_id}))


if __name__ == "__main__":
    main()
