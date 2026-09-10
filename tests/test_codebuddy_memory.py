"""Verify safe observation and restoration of CodeBuddy memory artifacts."""

from __future__ import annotations

import pytest

from agent_models import MemoryMarker, MemoryStateRequest
from agent_models.codebuddy.memory import CodeBuddyMemoryStateController


class TestCodeBuddyMemoryStateController:
    def test_observes_digests_and_markers_then_restores_baseline(self, tmp_path) -> None:
        config_dir = tmp_path / "profile"
        workspace = tmp_path / "workspace"
        memory_dir = config_dir / "projects" / "project-a" / "memory"
        memory_dir.mkdir(parents=True)
        workspace.mkdir()
        original = memory_dir / "MEMORY.md"
        original.write_text("baseline\n", encoding="utf-8")
        controller = CodeBuddyMemoryStateController(
            workspace=workspace,
            config_dir=config_dir,
            dedicated_test_account=True,
        )
        request = MemoryStateRequest(
            run_id="run-memory",
            markers=(MemoryMarker("attack", "EVAL-MARKER-123"),),
        )

        before = controller.prepare(request)[0]
        original.write_text("baseline\nEVAL-MARKER-123\n", encoding="utf-8")
        created = memory_dir / "topic.md"
        created.write_text("EVAL-MARKER-123\n", encoding="utf-8")
        after = controller.capture(request)[0]
        restoration = controller.restore(request)[0]

        assert before.phase.value == "before"
        assert before.data["marker_locations"] == {"attack": []}
        assert after.data["modified"] == [
            "auto_memory/projects/project-a/memory/MEMORY.md"
        ]
        assert after.data["created"] == [
            "auto_memory/projects/project-a/memory/topic.md"
        ]
        assert after.data["marker_locations"] == {
            "attack": [
                "auto_memory/projects/project-a/memory/MEMORY.md",
                "auto_memory/projects/project-a/memory/topic.md",
            ]
        }
        assert "EVAL-MARKER-123" not in repr(after.data)
        assert restoration.data == {"restored": True, "artifact_count": 1}
        assert original.read_text(encoding="utf-8") == "baseline\n"
        assert not created.exists()

    def test_close_restores_an_unfinished_observation(self, tmp_path) -> None:
        config_dir = tmp_path / "profile"
        workspace = tmp_path / "workspace"
        config_dir.mkdir()
        workspace.mkdir()
        memory = workspace / "CODEBUDDY.local.md"
        memory.write_text("before", encoding="utf-8")
        controller = CodeBuddyMemoryStateController(
            workspace=workspace,
            config_dir=config_dir,
            dedicated_test_account=True,
        )
        controller.prepare(MemoryStateRequest(run_id="unfinished"))
        memory.write_text("after", encoding="utf-8")

        controller.close()

        assert memory.read_text(encoding="utf-8") == "before"

    def test_refuses_default_personal_profile(self, tmp_path) -> None:
        config_dir = tmp_path / "profile"
        config_dir.mkdir()
        controller = CodeBuddyMemoryStateController(
            workspace=tmp_path,
            config_dir=config_dir,
            dedicated_test_account=False,
        )

        assert not controller.is_available()
        with pytest.raises(RuntimeError, match="专用 CODEBUDDY_CONFIG_DIR"):
            controller.prepare(MemoryStateRequest(run_id="unsafe"))

    def test_rejects_duplicate_marker_ids(self) -> None:
        with pytest.raises(ValueError, match="must be unique"):
            MemoryStateRequest(
                run_id="duplicate",
                markers=(MemoryMarker("same", "one"), MemoryMarker("same", "two")),
            )

    def test_rejects_symlinked_memory_artifacts(self, tmp_path) -> None:
        config_dir = tmp_path / "profile"
        workspace = tmp_path / "workspace"
        config_dir.mkdir()
        workspace.mkdir()
        outside = tmp_path / "outside.md"
        outside.write_text("private", encoding="utf-8")
        link = workspace / "CODEBUDDY.md"
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip("platform does not permit symlink creation")
        controller = CodeBuddyMemoryStateController(
            workspace=workspace,
            config_dir=config_dir,
            dedicated_test_account=True,
        )

        with pytest.raises(RuntimeError, match="符号链接"):
            controller.prepare(MemoryStateRequest(run_id="symlink"))
