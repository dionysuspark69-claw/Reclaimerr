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
#
# Note on "nobody's watched" templates: `include_never_watched=True`
# means "don't filter out never-watched items" (i.e. keep both watched
# and never-watched). To actually scope a rule to *only* never-watched
# items we also set `max_view_count=0`. Earlier versions of these
# templates set only `include_never_watched=True`, which had the
# opposite effect of the label — matching every item that met the
# age criterion regardless of watch state. `seed_template_rules`
# migrates affected rows on startup (see below).
_TEMPLATES: list[dict] = [
    dict(
        name="Template: low-rated movies nobody's watched",
        media_type=MediaType.MOVIE,
        enabled=False,
        include_never_watched=True,
        max_view_count=0,
        max_vote_average=5.0,
        min_vote_count=50,
        min_days_since_added=180,
    ),
    dict(
        name="Template: huge movies that sat untouched for a year",
        media_type=MediaType.MOVIE,
        enabled=False,
        include_never_watched=True,
        max_view_count=0,
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
        max_view_count=0,
        max_vote_count=20,
        max_popularity=5.0,
        min_days_since_added=365,
    ),
    dict(
        name="Template: stale series nobody's watched",
        media_type=MediaType.SERIES,
        enabled=False,
        include_never_watched=True,
        max_view_count=0,
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

# Fields on ReclaimRule that the template controls. When migrating a
# legacy row we reset exactly these and leave user-customizable fields
# (name, enabled, library_ids, timestamps, etc.) alone.
_CRITERIA_FIELDS = {
    "media_type",
    "include_never_watched",
    "min_view_count",
    "max_view_count",
    "min_popularity",
    "max_popularity",
    "min_vote_average",
    "max_vote_average",
    "min_vote_count",
    "max_vote_count",
    "min_days_since_added",
    "max_days_since_added",
    "min_days_since_last_watched",
    "max_days_since_last_watched",
    "min_size",
    "max_size",
}


def _has_legacy_unwatched_bug(rule: ReclaimRule, tpl: dict) -> bool:
    """Detect a template row that still has the pre-fix criteria.

    Pre-fix: `include_never_watched=True` with no `max_view_count`. Such
    rules match *every* item that meets the age criterion because
    `include_never_watched=True` does not restrict to never-watched
    items — it just refuses to filter them out. We only migrate when
    the template itself now pins `max_view_count=0`.
    """
    if tpl.get("max_view_count") != 0:
        return False
    return rule.include_never_watched is True and rule.max_view_count is None


async def seed_template_rules() -> int:
    """Insert any missing template rules and repair legacy buggy rows.

    Returns the count of rows inserted + migrated.
    """
    async with async_db() as session:
        existing_rows = (
            await session.execute(
                select(ReclaimRule).where(
                    ReclaimRule.name.in_([tpl["name"] for tpl in _TEMPLATES])
                )
            )
        ).scalars().all()
        existing_by_name = {r.name: r for r in existing_rows}

        inserted = 0
        migrated = 0
        for tpl in _TEMPLATES:
            existing = existing_by_name.get(tpl["name"])
            if existing is None:
                session.add(ReclaimRule(**tpl))
                inserted += 1
                continue
            if not _has_legacy_unwatched_bug(existing, tpl):
                continue
            # Row matches the legacy-buggy signature — reset criteria to
            # the current template. Preserve `enabled` and `library_ids`
            # so user choices (e.g. enabling the rule, restricting to
            # certain libraries) aren't thrown away.
            for field, value in tpl.items():
                if field in _CRITERIA_FIELDS:
                    setattr(existing, field, value)
            migrated += 1

        if inserted or migrated:
            await session.commit()
            if inserted:
                LOG.info(f"Seeded {inserted} template reclaim rules (disabled)")
            if migrated:
                LOG.info(
                    f"Migrated {migrated} legacy template rules to filter "
                    f"never-watched items only"
                )
        return inserted + migrated
