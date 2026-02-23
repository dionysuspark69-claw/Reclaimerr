from random import sample as random_sample

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import __version__
from backend.database import get_db
from backend.database.models import Movie, Series

from .default_backdrops import TOP_RATED_BACKDROPS

router = APIRouter(tags=["info"])


@router.get("/version")
async def get_version() -> dict[str, str]:
    """Get application version."""
    return {
        "version": str(__version__),
        "program": __version__.program_name,
        "url": __version__.program_url,
    }


@router.get("/random-backdrop")
async def get_backdrops(
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    """
    Get backdrop image URLs.
    If no backdrops are found in the database, return a random selection of default top-rated backdrops.
    """
    # count movies with a backdrop
    movie_count_stmt = (
        select(func.count()).select_from(Movie).where(Movie.backdrop_url.isnot(None))
    )
    series_count_stmt = (
        select(func.count()).select_from(Series).where(Series.backdrop_url.isnot(None))
    )

    movie_count = (await db.execute(movie_count_stmt)).scalar_one()
    series_count = (await db.execute(series_count_stmt)).scalar_one()
    total_count = movie_count + series_count

    if total_count == 0:
        return {"backdrops": random_sample(TOP_RATED_BACKDROPS, 5)}

    # fetch up to FETCH_LIMIT most popular backdrops from each
    FETCH_LIMIT = 30
    movie_stmt = (
        select(Movie.backdrop_url)
        .where(Movie.backdrop_url.isnot(None))
        .order_by(desc(Movie.popularity))
        .limit(FETCH_LIMIT)
    )
    series_stmt = (
        select(Series.backdrop_url)
        .where(Series.backdrop_url.isnot(None))
        .order_by(desc(Series.popularity))
        .limit(FETCH_LIMIT)
    )

    movie_backdrops = [row[0] for row in (await db.execute(movie_stmt)).all()]
    series_backdrops = [row[0] for row in (await db.execute(series_stmt)).all()]
    all_backdrops = [url for url in movie_backdrops + series_backdrops if url]

    if not all_backdrops or len(all_backdrops) < 5:
        return {"backdrops": random_sample(TOP_RATED_BACKDROPS, 5)}

    return {"backdrops": random_sample(all_backdrops, 5)}
