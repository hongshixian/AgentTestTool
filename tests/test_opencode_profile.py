"""Verify OpenCode test profiles exclude personal configuration and raw keys."""

import json
from pathlib import Path

import pytest

from agent_models.opencode.profile import OpenCodeTestProfile


def _source(tmp_path: Path, *, key_reference: str) -> Path:
    source = tmp_path / "source.json"
    source.write_text(json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "plugin": ["untrusted-example"],
        "provider": {
            "iiis": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": "https://example.invalid/v1", "apiKey": key_reference},
                "models": {"infi/deepseek-v4.1-flash": {"name": "Test"}},
            },
            "private": {"models": {"another": {}}},
        },
    }), encoding="utf-8")
    return source


def test_profile_isolates_selected_provider_and_secret(tmp_path: Path) -> None:
    key = tmp_path / "provider.key"
    key.write_text("obviously-fake-api-key\n", encoding="utf-8")
    source = _source(tmp_path, key_reference="{file:" + str(key) + "}")
    profile = OpenCodeTestProfile(source=source, environ={
        "JUDGE_API_KEY": "not-for-agent",
        "USERPROFILE": "C:\\Users\\personal-profile",
        "APPDATA": "C:\\Users\\personal-profile\\AppData\\Roaming",
        "LOCALAPPDATA": "C:\\Users\\personal-profile\\AppData\\Local",
    })
    try:
        config = json.loads(profile.config_file.read_text(encoding="utf-8"))
        assert config["model"] == "iiis/infi/deepseek-v4.1-flash"
        assert list(config["provider"]) == ["iiis"]
        assert "plugin" not in config
        assert "obviously-fake-api-key" not in profile.config_file.read_text()
        env = profile.process_environment(permission={"edit": "allow"})
        assert env["HOME"].startswith(str(profile.root))
        assert env["XDG_CONFIG_HOME"].startswith(str(profile.root))
        assert all(env[name].startswith(str(profile.root)) for name in (
            "USERPROFILE", "APPDATA", "LOCALAPPDATA",
        ))
        assert "JUDGE_API_KEY" not in env
        assert json.loads(env["OPENCODE_CONFIG_CONTENT"]) == {"permission": {"edit": "allow"}}
        profile.configure_mcp({"ats_mock": {"type": "local", "command": ["python", "mock.py"]}})
        assert "ats_mock" in json.loads(profile.config_file.read_text())["mcp"]
    finally:
        directory = profile.root
        profile.close()
        assert not directory.exists()


def test_profile_rejects_plaintext_secret_and_missing_model(tmp_path: Path) -> None:
    source = _source(tmp_path, key_reference="not-a-safe-reference")
    with pytest.raises(ValueError, match="file or env"):
        OpenCodeTestProfile(source=source)
    source = _source(tmp_path, key_reference="{env:EXAMPLE_KEY}")
    with pytest.raises(ValueError, match="not configured"):
        OpenCodeTestProfile(model="iiis/unknown", source=source)
    with pytest.raises(ValueError, match="API key is empty"):
        OpenCodeTestProfile(source=source, environ={})
