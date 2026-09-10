"""Product-neutral requests for observable persistent-memory state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryMarker:
    """Name a test value without persisting the value in collected evidence."""

    marker_id: str
    value: str

    def __post_init__(self) -> None:
        if not self.marker_id.strip():
            raise ValueError("memory marker id must be nonempty")
        if not self.value:
            raise ValueError("memory marker value must be nonempty")


@dataclass(frozen=True, slots=True)
class MemoryStateRequest:
    """Describe one bounded observation of product-visible memory artifacts."""

    run_id: str
    markers: tuple[MemoryMarker, ...] = ()

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("memory state run id must be nonempty")
        marker_ids = tuple(marker.marker_id for marker in self.markers)
        if len(set(marker_ids)) != len(marker_ids):
            raise ValueError("memory marker ids must be unique")
