from sqlalchemy import func, select

from backend.core.logger import LOG
from backend.database import async_db
from backend.database.models import ReclaimRule
from backend.enums import MediaType

_TEMPLATES: list[dict] = [
    dict(
        name="Template: low-rated movies nobody's watched",
        media_type=MediaType.MOVIE,
        enabled=False,
        include_never_watched=True,
        max_vote_average=5.0,
        min_vote_count=50,
        min_days_since_added=180,
    ),
    dict(
        name="Template: stale series nobody's watched",
        media_type=MediaType.SERIES,
        enabled=False,
        include_never_watched=True,
        min_days_since_added=365,
    ),
]


async def seed_template_rules() -> int:
    """Insert starter rules (disabled) only if the rules table is empty."""
    async with async_db() as session:
        count = (
            await session.execute(select(func.count(ReclaimRule.id)))
        ).scalar_one()
        if count and count > 0:
            return 0
        for tpl in _TEMPLATES:
            session.add(ReclaimRule(**tpl))
        await session.commit()
        LOG.info(f"Seeded {len(_TEMPLATES)} template reclaim rules (disabled)")
        return len(_TEMPLATES)
