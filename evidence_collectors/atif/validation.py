"""Local structural validation for the ATIF subset emitted by this project."""

from __future__ import annotations

import json

from evidence_collectors.atif.model import ATIF_SCHEMA_VERSION, AtifTrajectory


def validate_trajectory(trajectory: AtifTrajectory) -> None:
    payload = trajectory.to_payload()
    if payload["schema_version"] != ATIF_SCHEMA_VERSION:
        raise ValueError(f"unsupported ATIF schema version: {payload['schema_version']}")
    if not trajectory.session_id or not trajectory.trajectory_id:
        raise ValueError("ATIF session_id and trajectory_id must be nonempty")
    expected = list(range(1, len(trajectory.steps) + 1))
    actual = [step.step_id for step in trajectory.steps]
    if actual != expected:
        raise ValueError("ATIF step_id values must be sequential and start at 1")
    json.dumps(payload, allow_nan=False)
