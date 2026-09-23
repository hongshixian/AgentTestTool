"""Isolate OpenCode runs from the user's normal sessions and plugins."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from configs.environment import agent_process_environment
from agent_models.opencode.hooks.capture import OpenCodeHookCapture


DEFAULT_TEST_MODEL = "iiis/infi/deepseek-v4.1-flash"
_FILE_REFERENCE = re.compile(r"^\{file:([^{}]+)\}$")
_ENV_REFERENCE = re.compile(r"^\{env:([A-Za-z_][A-Za-z0-9_]*)\}$")


class OpenCodeTestProfile:
    """Copy only the selected provider into an ephemeral per-case profile."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_TEST_MODEL,
        source: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        provider_name, separator, model_name = model.partition("/")
        if not separator or not provider_name or not model_name:
            raise ValueError("OpenCode model must have provider/model format")
        source = source or Path.home() / ".config" / "opencode" / "opencode.json"
        if not source.is_file() or source.is_symlink():
            raise ValueError("OpenCode test provider configuration is unavailable")
        raw = json.loads(source.read_text(encoding="utf-8"))
        providers = raw.get("provider") if isinstance(raw, dict) else None
        provider = providers.get(provider_name) if isinstance(providers, dict) else None
        models = provider.get("models") if isinstance(provider, dict) else None
        if not isinstance(models, dict) or model_name not in models:
            raise ValueError(f"OpenCode test model is not configured: {model}")
        provider = copy.deepcopy(provider)
        options = provider.get("options")
        if not isinstance(options, dict):
            raise ValueError("OpenCode test provider has no options")
        api_key = options.get("apiKey")
        if not isinstance(api_key, str):
            raise ValueError("OpenCode test provider must reference an external API key")
        source_env = os.environ if environ is None else environ
        if match := _FILE_REFERENCE.fullmatch(api_key):
            source_key = Path(match.group(1)).expanduser()
            if not source_key.is_file() or source_key.is_symlink():
                raise ValueError("OpenCode test API key file is unavailable")
            secret = source_key.read_text(encoding="utf-8").strip()
            options["apiKey"] = "{file:" + str(source_key.resolve()) + "}"
        elif match := _ENV_REFERENCE.fullmatch(api_key):
            secret = source_env.get(match.group(1), "").strip()
        else:
            raise ValueError("OpenCode test provider must use a file or env API key reference")
        if not secret:
            raise ValueError("OpenCode test API key is empty")

        self.model = model
        self.secret = secret
        self.provider_base_url = str(options.get("baseURL") or "")
        self._launch_overrides: dict[str, str] = {}
        self._hook_capture: OpenCodeHookCapture | None = None
        self._hook_turn_id: str | None = None
        self._environ = dict(source_env)
        self._provider_name = provider_name
        self._provider = provider
        self._directory = tempfile.TemporaryDirectory(prefix="ats-opencode-")
        self.root = Path(self._directory.name)
        for name in ("home", "config/opencode", "data", "state", "cache", "roaming", "local"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.config_file = self.root / "config" / "opencode" / "opencode.json"
        self._write_config(mcp={}, tools={})

    def _write_config(self, *, mcp: Mapping[str, Any], tools: Mapping[str, bool]) -> None:
        data = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {self._provider_name: self._provider},
            "model": self.model,
        }
        if mcp:
            data["mcp"] = dict(mcp)
        if tools:
            data["tools"] = dict(tools)
        self.config_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.config_file.chmod(0o600)

    def configure_mcp(self, mcp: Mapping[str, Any], *, tools: Mapping[str, bool] | None = None) -> None:
        """Install evaluator-controlled MCP servers before the first turn."""
        self._write_config(mcp=mcp, tools=tools or {})

    def set_launch_overrides(self, overrides: Mapping[str, str]) -> None:
        """Apply run-local collector settings without touching the user's config."""
        allowed = {"HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "NODE_EXTRA_CA_CERTS"}
        if any(name not in allowed or not isinstance(value, str) for name, value in overrides.items()):
            raise ValueError("Unsupported OpenCode collector environment override")
        self._launch_overrides = dict(overrides)

    @property
    def hook_capture(self) -> OpenCodeHookCapture | None:
        return self._hook_capture

    def attach_hook_capture(self, capture: OpenCodeHookCapture) -> None:
        if self._hook_capture is not None:
            raise RuntimeError("OpenCode test hook capture is already installed")
        capture.install(isolated_config_dir=self.config_file.parent)
        self._hook_capture = capture

    def select_hook_turn(self, turn_id: str | None) -> None:
        self._hook_turn_id = turn_id

    def process_environment(self, *, permission: Mapping[str, Any] | None = None) -> dict[str, str]:
        result = agent_process_environment(self._environ)
        for name in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR", "OPENCODE_CONFIG_CONTENT"):
            result.pop(name, None)
        result.update({
            "HOME": str(self.root / "home"),
            "USERPROFILE": str(self.root / "home"),
            "APPDATA": str(self.root / "roaming"),
            "LOCALAPPDATA": str(self.root / "local"),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "OPENCODE_CONFIG_DIR": str(self.root / "config" / "opencode"),
        })
        if os.name == "nt":
            home = self.root / "home"
            result["HOMEDRIVE"] = home.drive
            result["HOMEPATH"] = str(home)[len(home.drive):]
        result.update(self._launch_overrides)
        if permission is not None:
            result["OPENCODE_CONFIG_CONTENT"] = json.dumps(
                {"permission": dict(permission)}, ensure_ascii=False
            )
        if self._hook_capture is not None:
            result = self._hook_capture.process_environment(
                result, case_level="grey_box", turn_id=self._hook_turn_id,
            )
        return result

    def close(self) -> None:
        self._directory.cleanup()
