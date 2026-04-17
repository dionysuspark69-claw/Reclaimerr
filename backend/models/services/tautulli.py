from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class TautulliWatchSummary:
    """Aggregated watch data for a single Plex item (keyed by Plex ratingKey)."""

    rating_key: str
    view_count: int
    last_viewed_at: datetime | None


# Generic alias — Plex's global-history overlay returns the same shape.
PlexWatchSummary = TautulliWatchSummary
