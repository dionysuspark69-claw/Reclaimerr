from enum import StrEnum, auto


class Service(StrEnum):
    SONARR = auto()
    RADARR = auto()
    JELLYFIN = auto()
    PLEX = auto()
    SEERR = auto()


class MediaType(StrEnum):
    MOVIE = auto()
    SERIES = auto()


class SeriesStatus(StrEnum):
    CONTINUING = auto()
    ENDED = auto()


class TaskStatus(StrEnum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
