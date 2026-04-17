from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logger import LOG
from backend.core.service_manager import service_manager
from backend.core.task_tracking import track_task_execution
from backend.database import async_db
from backend.database.models import (
    Movie,
    MovieVersion,
    ReclaimCandidate,
)
from backend.enums import MediaType, Task

__all__ = ["scan_tdarr_flagged"]

TDARR_RULE_ID = -1  # synthetic rule id for tdarr-sourced candidates
TDARR_REASON_PREFIX = "Tdarr flagged"


def _normalize_path(path: str | None) -> str | None:
    if not path:
        return None
    p = path.strip().lower()
    return p.rstrip("/")


async def _purge_stale_tdarr_candidates(db: AsyncSession) -> int:
    """Remove any pre-existing tdarr candidates so we reflect current state."""
    result = await db.execute(
        delete(ReclaimCandidate).where(
            ReclaimCandidate.matched_rule_ids.contains([TDARR_RULE_ID])
        )
    )
    return result.rowcount or 0  # type: ignore[reportAttributeAccessIssue]


async def _match_movie_for_path(
    db: AsyncSession, normalized_path: str
) -> Movie | None:
    """Find the Movie that owns a MovieVersion at this path."""
    result = await db.execute(
        select(Movie)
        .join(MovieVersion, MovieVersion.movie_id == Movie.id)
        .where(MovieVersion.path.ilike(f"%{normalized_path.rsplit('/', 1)[-1]}"))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def scan_tdarr_flagged() -> None:
    """Pull files Tdarr has flagged and surface them as ReclaimCandidates."""
    LOG.info("Starting Tdarr-flagged scan")

    async with track_task_execution(Task.SCAN_TDARR_FLAGGED):
        client = service_manager.tdarr
        if client is None:
            LOG.warning("Tdarr scan skipped: no Tdarr service configured")
            async with async_db() as db:
                purged = await _purge_stale_tdarr_candidates(db)
                if purged:
                    await db.commit()
            return

        try:
            flagged = await client.get_flagged_files()
        except Exception as e:
            LOG.error(f"Tdarr scan failed to fetch flagged files: {e}", exc_info=True)
            raise

        LOG.info(f"Tdarr returned {len(flagged)} flagged files")

        async with async_db() as db:
            await _purge_stale_tdarr_candidates(db)

            created = 0
            unmatched = 0
            now = datetime.now(timezone.utc)

            for file in flagged:
                normalized = _normalize_path(file.file_path)
                if not normalized:
                    unmatched += 1
                    continue
                movie = await _match_movie_for_path(db, normalized)
                if not movie:
                    unmatched += 1
                    continue

                space_gb = (
                    file.estimated_savings / (1024**3)
                    if file.estimated_savings
                    else (file.file_size / (1024**3) if file.file_size else None)
                )

                candidate = ReclaimCandidate(
                    media_type=MediaType.MOVIE,
                    matched_rule_ids=[TDARR_RULE_ID],
                    matched_criteria={
                        "tdarr_decision": file.reason,
                        "container": file.container,
                        "video_codec": file.video_codec,
                        "resolution": file.resolution,
                        "file_size": file.file_size,
                    },
                    reason=f"{TDARR_REASON_PREFIX}: {file.reason}",
                    movie_id=movie.id,
                    estimated_space_gb=space_gb,
                )
                candidate.updated_at = now  # type: ignore[assignment]
                db.add(candidate)
                created += 1

            await db.commit()

        LOG.info(
            f"Tdarr scan complete: {created} candidates created, "
            f"{unmatched} flagged files could not be matched to a known movie"
        )
