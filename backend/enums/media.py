from enum import StrEnum, auto


class Service(StrEnum):
    SONARR = auto()
    RADARR = auto()
    PLEX = auto()
    SEERR = auto()
    TAUTULLI = auto()
    TDARR = auto()


class MediaType(StrEnum):
    MOVIE = auto()
    SERIES = auto()


class ProtectionRequestStatus(StrEnum):
    PENDING = auto()
    APPROVED = auto()
    DENIED = auto()


class ReclaimSource(StrEnum):
    """Where a reclaim event originated, used for Reports breakdowns."""

    RULE_BASED = auto()  # scheduled rule match / Candidates page delete
    DUPLICATE = auto()  # Duplicates page resolve
    TDARR = auto()  # Tdarr-flagged candidate delete
    MANUAL = auto()  # user-initiated direct delete (fallback)
