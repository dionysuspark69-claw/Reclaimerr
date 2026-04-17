from sqlalchemy import select

from backend.core.logger import LOG
from backend.database import async_db
from backend.database.models import ReclaimRule
from backend.enums import MediaType

# Starter rules inserted on startup so new users have working examples.
# Each entry is inserted only if no rule with the same `name` already
# exists, so re-seeding is idempotent and user-created rules are never
# touched. If a user deletes a template it will reappear on the next
# startup — they can rename it (drop the "Template:" prefix) to opt
# out of future re-seeds.
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
        name="Template: huge movies that sat untouched for a year",
        media_type=MediaType.MOVIE,
        enabled=False,
        include_never_watched=True,
        min_size=10 * 1024 * 1024 * 1024,  # 10 GB
        min_days_since_added=365,
    ),
    dict(
        name="Template: movies watched once a long time ago",
        media_type=MediaType.MOVIE,
        enabled=False,
        include_never_watched=False,
        max_view_count=1,
        min_days_since_last_watched=730,  # not touched in 2 years
    ),
    dict(
        name="Template: obscure movies with no ratings signal",
        media_type=MediaType.MOVIE,
        enabled=False,
        include_never_watched=True,
        max_vote_count=20,
        max_popularity=5.0,
        min_days_since_added=365,
    ),
    dict(
        name="Template: stale series nobody's watched",
        media_type=MediaType.SERIES,
        enabled=False,
        include_never_watched=True,
        min_days_since_added=365,
    ),
    dict(
        name="Template: low-rated series nobody finished",
        media_type=MediaType.SERIES,
        enabled=False,
        include_never_watched=False,
        max_vote_average=6.0,
        min_days_since_last_watched=365,
    ),
]


async def seed_template_rules() -> int:
    """Insert any missing template rules (disabled by default)."""
    async with async_db() as session:
        existing = (
            await session.execute(
                select(ReclaimRule.name).where(
                    ReclaimRule.name.in_([tpl["name"] for tpl in _TEMPLATES])
                )
            )
        ).scalars().all()
        existing_names = set(existing)

        inserted = 0
        for tpl in _TEMPLATES:
            if tpl["name"] in existing_names:
                continue
            session.add(ReclaimRule(**tpl))
            inserted += 1

        if inserted:
            await session.commit()
            LOG.info(f"Seeded {inserted} template reclaim rules (disabled)")
        return inserted
