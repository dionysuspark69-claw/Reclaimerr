from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TdarrFlaggedFile:
    """A file Tdarr has flagged for transcode (oversized / wrong codec / etc.)."""

    id: str
    file_path: str
    library_id: str | None
    library_name: str | None
    container: str | None
    video_codec: str | None
    resolution: str | None
    file_size: int  # bytes
    estimated_savings: int  # bytes (best-effort; 0 when unknown)
    reason: str
    raw: dict | None = None
