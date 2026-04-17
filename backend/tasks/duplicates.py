from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.logger import LOG
from backend.core.task_tracking import track_task_execution
from backend.database import async_db
from backend.database.models import (
    DuplicateCandidate,
    DuplicateGroup,
    GeneralSettings,
    Movie,
    MovieVersion,
    Series,
    SeriesServiceRef,
)
from backend.enums import MediaType, Task
from backend.types import MEDIA_SERVERS

# Priority boost applied when a version lives in the admin's preferred library.
# Must dwarf resolution/size scores so the preferred library always wins.
_PREFERRED_LIBRARY_BOOST = 1_000_000_000

__all__ = ["scan_duplicates", "resolve_duplicate_groups"]


_RES_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("2160p", re.compile(r"\b(2160p|4k|uhd)\b", re.IGNORECASE)),
    ("1080p", re.compile(r"\b1080p\b", re.IGNORECASE)),
    ("720p", re.compile(r"\b720p\b", re.IGNORECASE)),
    ("480p", re.compile(r"\b480p\b", re.IGNORECASE)),
)


def _detect_resolution(path: str | None) -> str | None:
    """Best-effort resolution detection from a file path."""
    if not path:
        return None
    for label, pattern in _RES_PATTERNS:
        if pattern.search(path):
            return label
    return None


def _resolution_rank(resolution: str | None) -> int:
    """Higher rank = better quality."""
    return {"2160p": 4, "1080p": 3, "720p": 2, "480p": 1}.get(resolution or "", 0)


def _score_movie_version(
    version: MovieVersion, preferred_library_id: str | None = None
) -> tuple[float, str | None]:
    """Score a MovieVersion: higher = better candidate to keep.

    Default rule: highest resolution, tie-break on smallest size, then most
    recently added. If `preferred_library_id` matches, a huge constant boost
    is added so the preferred library always wins regardless of resolution.
    """
    resolution = _detect_resolution(version.path)
    res_score = _resolution_rank(resolution) * 1_000_000
    # When two have the same resolution, prefer the smaller (more efficient)
    # encode. Subtract size in MB so smaller wins.
    size_mb = (version.size or 0) / (1024 * 1024)
    size_score = -size_mb
    # Light weight on freshness so newer wins ties
    added_score = 0.0
    if version.added_at is not None:
        added_score = version.added_at.timestamp() / 1_000_000
    preferred_score = (
        _PREFERRED_LIBRARY_BOOST
        if preferred_library_id and version.library_id == preferred_library_id
        else 0
    )
    return res_score + size_score + added_score + preferred_score, resolution


async def _scan_movies(
    db: AsyncSession, preferred_library_id: str | None = None
) -> tuple[int, int]:
    """Scan movies for duplicates. Returns (groups_created, candidates_created)."""
    result = await db.execute(
        select(Movie)
        .where(Movie.removed_at.is_(None))
        .options(selectinload(Movie.versions))
    )
    movies = result.scalars().all()

    groups_created = 0
    candidates_created = 0

    for movie in movies:
        versions = list(movie.versions or [])
        if len(versions) < 2:
            continue

        # determine kind
        libraries = {v.library_id for v in versions}
        services = {v.service for v in versions}
        if len(libraries) > 1 or len(services) > 1:
            detection_kind = (
                "mixed" if len(versions) > len(libraries) else "cross_library"
            )
        else:
            detection_kind = "multi_version"

        scored: list[tuple[MovieVersion, float, str | None]] = [
            (v, *_score_movie_version(v, preferred_library_id)) for v in versions
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        keep_id = scored[0][0].id

        total_size = sum(v.size or 0 for v in versions)
        keep_size = scored[0][0].size or 0
        reclaimable = max(0, total_size - keep_size)

        group = DuplicateGroup(
            media_type=MediaType.MOVIE,
            movie_id=movie.id,
            series_id=None,
            title=movie.title,
            year=movie.year,
            detection_kind=detection_kind,
            candidate_count=len(versions),
            total_size=total_size,
            reclaimable_size=reclaimable,
            resolved=False,
        )
        db.add(group)
        await db.flush()
        groups_created += 1

        for version, score, resolution in scored:
            cand = DuplicateCandidate(
                group_id=group.id,
                movie_version_id=version.id,
                series_service_ref_id=None,
                service=version.service,
                library_id=version.library_id,
                library_name=version.library_name,
                path=version.path,
                size=version.size or 0,
                container=version.container,
                resolution=resolution,
                score=float(score),
                keep=(version.id == keep_id),
            )
            db.add(cand)
            candidates_created += 1

    return groups_created, candidates_created


async def _scan_series(db: AsyncSession) -> tuple[int, int]:
    """Scan series for cross-library duplicates only (no per-file versions)."""
    result = await db.execute(
        select(Series)
        .where(Series.removed_at.is_(None))
        .options(selectinload(Series.service_refs))
    )
    series_list = result.scalars().all()

    groups_created = 0
    candidates_created = 0

    for series in series_list:
        media_refs: list[SeriesServiceRef] = [
            r for r in (series.service_refs or []) if r.service in MEDIA_SERVERS
        ]
        if len(media_refs) < 2:
            continue

        libraries = {r.library_id for r in media_refs}
        services = {r.service for r in media_refs}
        if len(libraries) > 1 or len(services) > 1:
            detection_kind = "cross_library"
        else:
            continue

        # series have no per-file size on the ref; use series.size as a hint
        per_copy_size = int((series.size or 0) / max(1, len(media_refs)))
        total_size = (series.size or 0)
        # We can't truly estimate reclaimable for series; use (n-1)/n share
        reclaimable = per_copy_size * max(0, len(media_refs) - 1)

        # pick the first as the kept copy (operator confirms in UI)
        keep_ref_id = media_refs[0].id

        group = DuplicateGroup(
            media_type=MediaType.SERIES,
            movie_id=None,
            series_id=series.id,
            title=series.title,
            year=series.year,
            detection_kind=detection_kind,
            candidate_count=len(media_refs),
            total_size=total_size,
            reclaimable_size=reclaimable,
            resolved=False,
        )
        db.add(group)
        await db.flush()
        groups_created += 1

        for ref in media_refs:
            cand = DuplicateCandidate(
                group_id=group.id,
                movie_version_id=None,
                series_service_ref_id=ref.id,
                service=ref.service,
                library_id=ref.library_id,
                library_name=ref.library_name,
                path=ref.path,
                size=per_copy_size,
                container=None,
                resolution=None,
                score=0.0,
                keep=(ref.id == keep_ref_id),
            )
            db.add(cand)
            candidates_created += 1

    return groups_created, candidates_created


async def _clear_existing_groups(db: AsyncSession) -> None:
    """Wipe previous scan results so we reflect current state."""
    await db.execute(delete(DuplicateCandidate))
    await db.execute(delete(DuplicateGroup))


async def resolve_duplicate_groups(group_ids: list[int]) -> tuple[int, int, int]:
    """Delete the non-keep candidates in each group via Plex.

    Returns (files_deleted, files_failed, groups_resolved).
    """
    from backend.core.service_manager import service_manager

    if not group_ids:
        return 0, 0, 0

    plex = service_manager.plex
    if plex is None:
        LOG.warning("Cannot resolve duplicates: Plex service not configured")
        return 0, len(group_ids), 0

    deleted = 0
    failed = 0
    groups_resolved = 0

    async with async_db() as db:
        result = await db.execute(
            select(DuplicateGroup)
            .where(DuplicateGroup.id.in_(group_ids))
            .options(selectinload(DuplicateGroup.candidates))
        )
        groups = result.scalars().all()

        for group in groups:
            cands = list(group.candidates or [])
            to_delete = [c for c in cands if not c.keep]
            if not to_delete:
                continue

            group_failed = False
            seen_item_ids: set[str] = set()

            for cand in to_delete:
                rating_key: str | None = None
                if cand.movie_version_id is not None:
                    mv_res = await db.execute(
                        select(MovieVersion).where(
                            MovieVersion.id == cand.movie_version_id
                        )
                    )
                    mv = mv_res.scalar_one_or_none()
                    if mv is not None:
                        rating_key = mv.service_item_id
                elif cand.series_service_ref_id is not None:
                    ref_res = await db.execute(
                        select(SeriesServiceRef).where(
                            SeriesServiceRef.id == cand.series_service_ref_id
                        )
                    )
                    ref = ref_res.scalar_one_or_none()
                    if ref is not None:
                        rating_key = ref.service_id

                if not rating_key:
                    failed += 1
                    group_failed = True
                    continue

                if rating_key in seen_item_ids:
                    deleted += 1
                    continue
                seen_item_ids.add(rating_key)

                try:
                    await plex.delete_item(rating_key)
                    deleted += 1
                except Exception as e:
                    LOG.error(
                        f"Failed to delete duplicate candidate (rating_key={rating_key}): {e}"
                    )
                    failed += 1
                    group_failed = True

            if not group_failed:
                group.resolved = True
                groups_resolved += 1

        await db.commit()

    LOG.info(
        f"Resolved {groups_resolved}/{len(group_ids)} duplicate groups: "
        f"{deleted} files deleted, {failed} failed"
    )
    return deleted, failed, groups_resolved


async def scan_duplicates() -> None:
    """Entry point: scan all libraries for duplicates and persist groups."""
    LOG.info("Starting duplicate finder scan")

    async with track_task_execution(Task.FIND_DUPLICATES):
        try:
            async with async_db() as db:
                preferred = (
                    await db.execute(select(GeneralSettings.preferred_library_id))
                ).scalar_one_or_none()

                await _clear_existing_groups(db)
                await db.commit()

                m_groups, m_cands = await _scan_movies(db, preferred)
                await db.commit()

                s_groups, s_cands = await _scan_series(db)
                await db.commit()

            LOG.info(
                f"Duplicate scan complete: {m_groups} movie groups "
                f"({m_cands} versions), {s_groups} series groups ({s_cands} refs)"
            )
        except Exception as e:
            LOG.error(f"Error scanning duplicates: {e}", exc_info=True)
            raise
