from typing import Literal

from backend.enums import Service

MediaServerType = Literal[Service.PLEX]
MEDIA_SERVERS = frozenset[Service]({Service.PLEX})
