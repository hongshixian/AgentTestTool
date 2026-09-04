"""Product-neutral requests for controlled local-state tampering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_models.evidence import JsonValue, RequestContext


class LocalStateAction(str, Enum):
    PREPARE = "prepare"
    RESTORE = "restore"


class LocalStateKind(str, Enum):
    JSON = "json"
    KEY_VALUE = "key_value"


@dataclass(frozen=True, slots=True)
class LocalStateRequest:
    sample_id: str
    prompt_id: str
    repeat_index: int
    run_id: str
    device: str
    kind: LocalStateKind
    target_instance_id: str
    context: RequestContext

    def provider_payload(self, action: LocalStateAction) -> dict[str, JsonValue]:
        return {
            "action": action.value,
            "sample_id": self.sample_id,
            "prompt_id": self.prompt_id,
            "repeat_index": self.repeat_index,
            "run_id": self.run_id,
            "device": self.device,
            "storage_kind": self.kind.value,
            "target_instance_id": self.target_instance_id,
            "request_context": self.context.provider_payload(),
        }
