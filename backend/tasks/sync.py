from sqlalchemy import select

from backend.core.logger import LOG
from backend.core.service_manager import service_manager
from backend.database.database import async_db
from backend.database.models import ServiceConfig
from backend.enums import Service
from backend.models.media import AggregatedMovieData
from backend.services.jellyfin import JellyfinService
from backend.services.plex import PlexService


async def sync_movies():
    """
    Fetch and combine movies from all configured media servers, deduplicating by TMDB ID. Only
    grabs libraries that are included in the service configuration.
    """
    # fetch service configs from database to generate combined aggregated movie list
    aggregated_movies = []
    async with async_db() as session:
        # get all enabled media servers with valid configs
        query = select(ServiceConfig).where(
            ServiceConfig.service_type.in_((Service.PLEX, Service.JELLYFIN)),
            ServiceConfig.enabled.is_(True),
            ServiceConfig.base_url.isnot(None),
            ServiceConfig.api_key.isnot(None),
        )
        result = await session.execute(query)
        media_servers = result.scalars()

        # fetch movies from each media server
        for server in media_servers:
            # get service instance (ensuring initialized and a supported media server)
            service = await service_manager.return_service(server.service_type)
            if not service:
                LOG.error(f"Service {server.service_type} not initialized")
                continue
            if not isinstance(service, (JellyfinService, PlexService)):
                LOG.error(f"Service {server.service_type} is not a media server")
                continue
            LOG.debug(
                f"Fetching movies from {server.service_type} at {server.base_url}"
            )

            # fetch aggregated movies
            extra_settings = server.extra_settings
            get_movies = await service.get_aggregated_movies(
                included_libraries=extra_settings.get("included_libraries")
                if extra_settings
                else None
            )
            if get_movies:
                aggregated_movies.extend(get_movies)
            LOG.debug(f"Fetched {len(get_movies)} movies from {server.service_type}")

    # deduplicate movies, keeping the one with most recent watch date
    unique_movies: dict[str, AggregatedMovieData] = {}

    for movie in aggregated_movies:
        ext_ids = movie.external_ids
        if not ext_ids or not ext_ids.tmdb:
            continue

        tmdb_id = ext_ids.tmdb
        if tmdb_id not in unique_movies:
            unique_movies[tmdb_id] = movie
        else:
            # keep movie with most recent watch date (None is considered oldest)
            existing = unique_movies[tmdb_id]
            if movie.last_viewed_at and (
                not existing.last_viewed_at
                or movie.last_viewed_at > existing.last_viewed_at
            ):
                unique_movies[tmdb_id] = movie

    print(f"Total unique movies combined: {len(unique_movies)}")
    # print(unique_movies)
    last_item = unique_movies.popitem()
    # print(f"Removed item: {last_item}")
    
    # TODO: fill new movie data in the database and delete old entries


async def sync_with_media_servers():
    await sync_movies()


# async def reset_seerr_requests(deleted_items: list[dict]):
#     """
#     Reset requests in Seerr for deleted media items.

#     Args:
#         deleted_items: List of deleted media items with metadata
#     """
#     logger.info(f"Resetting Seerr requests for {len(deleted_items)} deleted items")

#     try:
#         # TODO: Implement Seerr request reset logic
#         # 1. For each deleted item, find corresponding request in Seerr
#         # 2. Reset/decline the request with appropriate message
#         # 3. Log results

#         logger.info("Seerr request reset completed successfully")
#     except Exception as e:
#         logger.error(f"Error resetting Seerr requests: {e}", exc_info=True)
