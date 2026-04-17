from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.auth import get_current_user, has_permission
from backend.core.utils.datetime_utils import to_utc_isoformat
from backend.database import get_db
from backend.database.models import (
    DuplicateCandidate,
    DuplicateGroup,
    Movie,
    ProtectedMedia,
    ProtectionRequest,
    ReclaimCandidate,
    ReclaimRule,
    Season,
    Series,
    User,
)
from backend.enums import MediaType, Permission, ProtectionRequestStatus, Task, UserRole
from backend.models.media import (
    CandidateEntry,
    DeleteCandidatesRequest,
    DeleteCandidatesResponse,
    DuplicateCandidateEntry,
    DuplicateGroupEntry,
    MatchedRuleRef,
    MediaStatusInfo,
    MovieVersionResponse,
    MovieWithStatus,
    PaginatedCandidatesResponse,
    PaginatedDuplicatesResponse,
    PaginatedMediaResponse,
    ResolveDuplicatesRequest,
    ResolveDuplicatesResponse,
    SeasonWithStatus,
    SeriesServiceRefResponse,
    SeriesWithStatus,
)
from backend.tasks.cleanup import delete_specific_candidates
from backend.tasks.duplicates import resolve_duplicate_groups

router = APIRouter(prefix="/api/media", tags=["media"])


def extract_genre_names(genres: list[dict] | None) -> list[str] | None:
    """
    Extract genre names from TMDB genre objects.

    Comes in format [{'id': 16, 'name': 'Animation'}, ...] but we only want the names.
    """
    if not genres:
        return None
    return [g["name"] for g in genres]


@router.get("/movies", response_model=PaginatedMediaResponse)
async def get_movies(
    _user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = Query("title", pattern="^(title|added_at|size|vote_average|year)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, max_length=200),
    candidates_only: bool = Query(False),
):
    """
    Get all movies with status information.

    Includes whether each movie is:
    - A deletion candidate
    - Protected
    - Has pending exception request
    """
    # build base query
    query = (
        select(Movie)
        .where(Movie.removed_at.is_(None))
        .options(selectinload(Movie.versions))
    )
    count_query = (
        select(func.count()).select_from(Movie).where(Movie.removed_at.is_(None))
    )

    # apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(Movie.title.ilike(search_term))
        count_query = count_query.where(Movie.title.ilike(search_term))

    # apply candidates filter
    # Note: use distinct() to guard against row multiplication if a movie ever ends up
    # with more than one ReclaimCandidate row (this should really not ever happen)
    if candidates_only:
        query = query.join(
            ReclaimCandidate, ReclaimCandidate.movie_id == Movie.id
        ).distinct()
        count_query = count_query.join(
            ReclaimCandidate, ReclaimCandidate.movie_id == Movie.id
        ).distinct()

    # apply sorting
    order_column = getattr(Movie, sort_by)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # get total count
    total = (await db.execute(count_query)).scalar_one()

    # apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    # execute query
    result = await db.execute(query)
    movies = result.scalars().all()

    # fetch status information for all movies
    movie_ids = [m.id for m in movies]

    # get candidates
    candidates_result = await db.execute(
        select(ReclaimCandidate).where(ReclaimCandidate.movie_id.in_(movie_ids))
    )
    candidates = {c.movie_id: c for c in candidates_result.scalars().all()}

    # get protected entries
    now = datetime.now(timezone.utc)
    protected_result = await db.execute(
        select(ProtectedMedia).where(
            ProtectedMedia.movie_id.in_(movie_ids),
            or_(
                ProtectedMedia.permanent.is_(True),
                ProtectedMedia.expires_at.is_(None),
                ProtectedMedia.expires_at > now,
            ),
        )
    )
    protected = {b.movie_id: b for b in protected_result.scalars().all()}

    # get exception requests
    requests_result = await db.execute(
        select(ProtectionRequest).where(
            ProtectionRequest.movie_id.in_(movie_ids),
            ProtectionRequest.status == ProtectionRequestStatus.PENDING,
        )
    )
    requests = {r.movie_id: r for r in requests_result.scalars().all()}

    # build response with status
    items = []
    for movie in movies:
        candidate = candidates.get(movie.id)
        protection_entry = protected.get(movie.id)
        request = requests.get(movie.id)

        status = MediaStatusInfo(
            is_candidate=candidate is not None,
            candidate_id=candidate.id if candidate else None,
            candidate_reason=candidate.reason if candidate else None,
            candidate_space_gb=candidate.estimated_space_gb if candidate else None,
            is_protected=protection_entry is not None,
            protected_reason=protection_entry.reason if protection_entry else None,
            protected_permanent=protection_entry.permanent
            if protection_entry
            else True,
            has_pending_request=request is not None,
            request_id=request.id if request else None,
            request_status=request.status if request else None,
            request_reason=request.reason if request else None,
        )

        movie_dict = {
            "id": movie.id,
            "title": movie.title,
            "year": movie.year,
            "tmdb_id": movie.tmdb_id,
            "size": movie.size,
            "versions": [
                MovieVersionResponse(
                    id=v.id,
                    service=v.service.value,
                    service_item_id=v.service_item_id,
                    service_media_id=v.service_media_id,
                    library_id=v.library_id,
                    library_name=v.library_name,
                    path=v.path,
                    size=v.size,
                    added_at=to_utc_isoformat(v.added_at),
                    container=v.container,
                )
                for v in movie.versions
            ],
            "radarr_id": movie.radarr_id,
            "imdb_id": movie.imdb_id,
            "tmdb_title": movie.tmdb_title,
            "original_title": movie.original_title,
            "tmdb_release_date": to_utc_isoformat(movie.tmdb_release_date),
            "original_language": movie.original_language,
            "poster_url": movie.poster_url,
            "backdrop_url": movie.backdrop_url,
            "overview": movie.overview,
            "genres": extract_genre_names(movie.genres),  # type: ignore
            "popularity": movie.popularity,
            "vote_average": movie.vote_average,
            "vote_count": movie.vote_count,
            "runtime": movie.runtime,
            "tagline": movie.tagline,
            "last_viewed_at": to_utc_isoformat(movie.last_viewed_at),
            "view_count": movie.view_count,
            "never_watched": movie.never_watched,
            "status": status,
            "added_at": to_utc_isoformat(movie.added_at),
        }
        items.append(MovieWithStatus(**movie_dict))

    total_pages = (total + per_page - 1) // per_page

    return PaginatedMediaResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/series", response_model=PaginatedMediaResponse)
async def get_series(
    _user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort_by: str = Query("title", pattern="^(title|added_at|size|vote_average|year)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, max_length=200),
    candidates_only: bool = Query(False),
):
    """
    Get all series with status information.

    Includes whether each series is:
    - A deletion candidate
    - Protected
    - Has pending exception request
    """
    # build base query
    query = (
        select(Series)
        .where(Series.removed_at.is_(None))
        .options(selectinload(Series.service_refs))
    )
    count_query = (
        select(func.count()).select_from(Series).where(Series.removed_at.is_(None))
    )

    # apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(Series.title.ilike(search_term))
        count_query = count_query.where(Series.title.ilike(search_term))

    # apply candidates filter
    # Note: we're using distinct() to avoid row multiplication when a series has multiple
    # season level candidates (each shares the same series_id)
    if candidates_only:
        query = query.join(
            ReclaimCandidate, ReclaimCandidate.series_id == Series.id
        ).distinct()
        count_query = count_query.join(
            ReclaimCandidate, ReclaimCandidate.series_id == Series.id
        ).distinct()

    # apply sorting
    order_column = getattr(Series, sort_by)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # get total count
    total = (await db.execute(count_query)).scalar_one()

    # apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    # execute query
    result = await db.execute(query)
    series_list = result.scalars().all()

    # fetch status information for all series
    series_ids = [s.id for s in series_list]

    # get series level candidates (no season)
    candidates_result = await db.execute(
        select(ReclaimCandidate).where(
            ReclaimCandidate.series_id.in_(series_ids),
            ReclaimCandidate.season_id.is_(None),
        )
    )
    candidates = {c.series_id: c for c in candidates_result.scalars().all()}

    # collect series_ids that have at least one season level candidate
    season_cands_result = await db.execute(
        select(ReclaimCandidate.series_id).where(
            ReclaimCandidate.series_id.in_(series_ids),
            ReclaimCandidate.season_id.isnot(None),
        )
    )
    series_with_season_cands: set[int] = {
        row[0] for row in season_cands_result.all() if row[0] is not None
    }

    # get protected entries
    now = datetime.now(timezone.utc)
    protected_result = await db.execute(
        select(ProtectedMedia).where(
            ProtectedMedia.series_id.in_(series_ids),
            or_(
                ProtectedMedia.permanent.is_(True),
                ProtectedMedia.expires_at.is_(None),
                ProtectedMedia.expires_at > now,
            ),
        )
    )
    protected = {b.series_id: b for b in protected_result.scalars().all()}

    # get exception requests
    requests_result = await db.execute(
        select(ProtectionRequest).where(
            ProtectionRequest.series_id.in_(series_ids),
            ProtectionRequest.status == ProtectionRequestStatus.PENDING,
        )
    )
    requests = {r.series_id: r for r in requests_result.scalars().all()}

    # build response with status
    items = []
    for series in series_list:
        candidate = candidates.get(series.id)
        protection_entry = protected.get(series.id)
        request = requests.get(series.id)

        status = MediaStatusInfo(
            is_candidate=candidate is not None,
            candidate_id=candidate.id if candidate else None,
            candidate_reason=candidate.reason if candidate else None,
            candidate_space_gb=candidate.estimated_space_gb if candidate else None,
            is_protected=protection_entry is not None,
            protected_reason=protection_entry.reason if protection_entry else None,
            protected_permanent=protection_entry.permanent
            if protection_entry
            else True,
            has_pending_request=request is not None,
            request_id=request.id if request else None,
            request_status=request.status if request else None,
            request_reason=request.reason if request else None,
        )

        series_dict = {
            "id": series.id,
            "title": series.title,
            "year": series.year,
            "tmdb_id": series.tmdb_id,
            "size": series.size,
            "service_refs": [
                SeriesServiceRefResponse(
                    service=ref.service.value,
                    service_id=ref.service_id,
                    library_id=ref.library_id,
                    library_name=ref.library_name,
                    path=ref.path,
                )
                for ref in series.service_refs
            ],
            "sonarr_id": series.sonarr_id,
            "imdb_id": series.imdb_id,
            "tvdb_id": series.tvdb_id,
            "tmdb_title": series.tmdb_title,
            "original_title": series.original_title,
            "tmdb_first_air_date": to_utc_isoformat(series.tmdb_first_air_date),
            "tmdb_last_air_date": to_utc_isoformat(series.tmdb_last_air_date),
            "original_language": series.original_language,
            "poster_url": series.poster_url,
            "backdrop_url": series.backdrop_url,
            "overview": series.overview,
            "genres": extract_genre_names(series.genres),  # type: ignore
            "popularity": series.popularity,
            "vote_average": series.vote_average,
            "vote_count": series.vote_count,
            "season_count": series.season_count,
            "tagline": series.tagline,
            "last_viewed_at": to_utc_isoformat(series.last_viewed_at),
            "view_count": series.view_count,
            "never_watched": series.never_watched,
            "status": status,
            "has_season_candidates": series.id in series_with_season_cands
            and candidate is None,
            "added_at": to_utc_isoformat(series.added_at),
        }
        items.append(SeriesWithStatus(**series_dict))

    total_pages = (total + per_page - 1) // per_page

    return PaginatedMediaResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/series/{series_id}/seasons", response_model=list[SeasonWithStatus])
async def get_series_seasons(
    series_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get per-season status for a series."""
    series_result = await db.execute(
        select(Series).where(Series.id == series_id, Series.removed_at.is_(None))
    )
    if series_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Series not found"
        )

    seasons_result = await db.execute(
        select(Season)
        .where(Season.series_id == series_id)
        .order_by(Season.season_number)
    )
    seasons = seasons_result.scalars().all()

    season_ids = [s.id for s in seasons]
    if not season_ids:
        return []

    # season level reclaim candidates
    cand_result = await db.execute(
        select(ReclaimCandidate).where(ReclaimCandidate.season_id.in_(season_ids))
    )
    season_candidates = {c.season_id: c for c in cand_result.scalars().all()}

    # season level protection entries
    now = datetime.now(timezone.utc)
    prot_result = await db.execute(
        select(ProtectedMedia).where(
            ProtectedMedia.season_id.in_(season_ids),
            or_(
                ProtectedMedia.permanent.is_(True),
                ProtectedMedia.expires_at.is_(None),
                ProtectedMedia.expires_at > now,
            ),
        )
    )
    season_protected = {p.season_id: p for p in prot_result.scalars().all()}

    items: list[SeasonWithStatus] = []
    for season in seasons:
        cand = season_candidates.get(season.id)
        prot = season_protected.get(season.id)
        season_status = MediaStatusInfo(
            is_candidate=cand is not None,
            candidate_id=cand.id if cand else None,
            candidate_reason=cand.reason if cand else None,
            candidate_space_gb=cand.estimated_space_gb if cand else None,
            is_protected=prot is not None,
            protected_reason=prot.reason if prot else None,
            protected_permanent=prot.permanent if prot else True,
        )
        items.append(
            SeasonWithStatus(
                id=season.id,
                season_number=season.season_number,
                episode_count=season.episode_count,
                size=season.size,
                view_count=season.view_count or 0,
                last_viewed_at=to_utc_isoformat(season.last_viewed_at),
                never_watched=season.never_watched
                if season.never_watched is not None
                else True,
                air_date=to_utc_isoformat(season.air_date),
                status=season_status,
            )
        )

    return items


@router.get("/candidates", response_model=PaginatedCandidatesResponse)
async def get_candidates(
    _user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=200),
    sort_by: str = Query(
        "created_at",
        pattern="^(created_at|media_title|estimated_space_gb)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, max_length=200),
    media_type: MediaType | None = Query(None),
    rule_id: int | None = Query(
        None,
        description=(
            "Filter candidates to those matched by a specific rule. "
            "Pass -1 to filter to Tdarr-flagged candidates."
        ),
    ),
):
    """Get all reclaim candidates with media info and pending request status."""
    base_query = (
        select(
            ReclaimCandidate,
            Movie.title.label("movie_title"),
            Movie.year.label("movie_year"),
            Movie.poster_url.label("movie_poster_url"),
            Series.title.label("series_title"),
            Series.year.label("series_year"),
            Series.poster_url.label("series_poster_url"),
            Season.season_number.label("season_number"),
        )
        .outerjoin(Movie, ReclaimCandidate.movie_id == Movie.id)
        .outerjoin(Series, ReclaimCandidate.series_id == Series.id)
        .outerjoin(Season, ReclaimCandidate.season_id == Season.id)
    )

    if media_type:
        base_query = base_query.where(ReclaimCandidate.media_type == media_type)

    if rule_id is not None:
        base_query = base_query.where(
            ReclaimCandidate.matched_rule_ids.contains([rule_id])
        )

    if search:
        search_term = f"%{search}%"
        base_query = base_query.where(
            or_(
                Movie.title.ilike(search_term),
                Series.title.ilike(search_term),
                ReclaimCandidate.reason.ilike(search_term),
            )
        )

    count_query = (
        select(func.count(ReclaimCandidate.id))
        .outerjoin(Movie, ReclaimCandidate.movie_id == Movie.id)
        .outerjoin(Series, ReclaimCandidate.series_id == Series.id)
        .outerjoin(Season, ReclaimCandidate.season_id == Season.id)
    )

    if media_type:
        count_query = count_query.where(ReclaimCandidate.media_type == media_type)

    if rule_id is not None:
        count_query = count_query.where(
            ReclaimCandidate.matched_rule_ids.contains([rule_id])
        )

    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            or_(
                Movie.title.ilike(search_term),
                Series.title.ilike(search_term),
                ReclaimCandidate.reason.ilike(search_term),
            )
        )

    total = (await db.execute(count_query)).scalar_one() or 0

    media_title_expr = func.coalesce(Movie.title, Series.title)
    if sort_by == "media_title":
        order_expr = media_title_expr
    elif sort_by == "estimated_space_gb":
        order_expr = ReclaimCandidate.estimated_space_gb
    else:
        order_expr = ReclaimCandidate.created_at

    if sort_order == "desc":
        order_expr = order_expr.desc()
    else:
        order_expr = order_expr.asc()

    offset = (page - 1) * per_page
    result = await db.execute(
        base_query.order_by(order_expr).offset(offset).limit(per_page)
    )
    rows = result.all()

    # collect IDs to check for pending exception requests in one query each
    movie_ids = [
        r.ReclaimCandidate.movie_id for r in rows if r.ReclaimCandidate.movie_id
    ]
    series_ids = [
        r.ReclaimCandidate.series_id for r in rows if r.ReclaimCandidate.series_id
    ]

    pending_movies: set[int] = set()
    pending_series: set[int] = set()

    if movie_ids:
        req_result = await db.execute(
            select(ProtectionRequest.movie_id).where(
                ProtectionRequest.movie_id.in_(movie_ids),
                ProtectionRequest.status == ProtectionRequestStatus.PENDING,
            )
        )
        pending_movies = {r[0] for r in req_result.all()}

    if series_ids:
        req_result = await db.execute(
            select(ProtectionRequest.series_id).where(
                ProtectionRequest.series_id.in_(series_ids),
                ProtectionRequest.status == ProtectionRequestStatus.PENDING,
            )
        )
        pending_series = {r[0] for r in req_result.all()}

    # Resolve rule names for the candidates in this page in one query so
    # the UI can show "picked up by <rule name>" badges instead of parsing
    # the reason string. Tdarr-sourced candidates carry a synthetic rule
    # id of -1 which won't match any real row.
    rule_id_set: set[int] = set()
    for row in rows:
        for rid in row.ReclaimCandidate.matched_rule_ids or []:
            if rid > 0:
                rule_id_set.add(rid)

    rule_name_by_id: dict[int, str] = {}
    if rule_id_set:
        rule_rows = await db.execute(
            select(ReclaimRule.id, ReclaimRule.name).where(
                ReclaimRule.id.in_(rule_id_set)
            )
        )
        rule_name_by_id = {rid: name for rid, name in rule_rows.all()}

    items_out: list[CandidateEntry] = []
    for row in rows:
        c = row.ReclaimCandidate
        is_movie = c.media_type is MediaType.MOVIE
        media_id = c.movie_id if is_movie else c.series_id
        media_title = row.movie_title if is_movie else row.series_title
        media_year = row.movie_year if is_movie else row.series_year
        poster_url = row.movie_poster_url if is_movie else row.series_poster_url
        has_pending = (
            c.movie_id in pending_movies if is_movie else c.series_id in pending_series
        )

        if media_id is None or media_title is None:
            continue

        matched_ids = c.matched_rule_ids or []
        source = "tdarr" if -1 in matched_ids else "rule"
        matched_rules = [
            MatchedRuleRef(id=rid, name=rule_name_by_id[rid])
            for rid in matched_ids
            if rid in rule_name_by_id
        ]

        items_out.append(
            CandidateEntry(
                id=c.id,
                media_type=c.media_type.value,
                media_id=media_id,
                media_title=media_title,
                media_year=media_year,
                poster_url=poster_url,
                reason=c.reason,
                source=source,
                matched_rules=matched_rules,
                estimated_space_gb=c.estimated_space_gb,
                has_pending_request=has_pending,
                created_at=to_utc_isoformat(c.created_at) or "",
                season_id=c.season_id,
                season_number=row.season_number,
                series_title=row.series_title if c.season_id is not None else None,
            )
        )

    total_pages = (total + per_page - 1) // per_page if total else 0
    return PaginatedCandidatesResponse(
        items=items_out,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.post("/candidates/delete", response_model=DeleteCandidatesResponse)
async def delete_candidates(
    request: DeleteCandidatesRequest,
    user: Annotated[User, Depends(get_current_user)],
    _db: AsyncSession = Depends(get_db),
):
    """Delete specific reclaim candidates, removing them from Radarr/Sonarr/Plex/Jellyfin.

    Requires admin or manage_reclaim permission. Uses same deletion priority as
    the automated task: Radarr/Sonarr first, then Jellyfin/Plex fallback.
    """
    if not (
        user.role is UserRole.ADMIN or has_permission(user, Permission.MANAGE_RECLAIM)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manage reclaim permission required",
        )

    if not request.candidate_ids:
        return DeleteCandidatesResponse(deleted=0, failed=0)

    deleted, failed = await delete_specific_candidates(
        request.candidate_ids, user_id=user.id
    )
    return DeleteCandidatesResponse(deleted=deleted, failed=failed)


@router.post("/scan-duplicates")
async def scan_duplicates_route(
    user: Annotated[User, Depends(get_current_user)],
):
    """Enqueue a duplicate-finder scan. Returns whether it was newly queued."""
    if not (
        user.role is UserRole.ADMIN or has_permission(user, Permission.MANAGE_RECLAIM)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manage reclaim permission required",
        )
    # Local import to avoid circular dependency at module load time.
    from backend.core.task_runtime import request_task_run

    job, queued = await request_task_run(Task.FIND_DUPLICATES)
    return {
        "queued": queued,
        "job_id": job.id if job is not None else None,
    }


@router.post("/scan-everything")
async def scan_everything_route(
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Enqueue every reclaim scan at once (rules, duplicates, Tdarr).

    Tdarr is skipped when the service isn't configured. Returns a per-task
    map so the UI can poll each job and report combined progress.
    """
    if not (
        user.role is UserRole.ADMIN or has_permission(user, Permission.MANAGE_RECLAIM)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manage reclaim permission required",
        )

    from backend.core.task_runtime import request_task_run
    from backend.database.models import ServiceConfig
    from backend.enums import Service

    tasks_to_run: list[Task] = [
        Task.SCAN_CLEANUP_CANDIDATES,
        Task.FIND_DUPLICATES,
    ]

    # Only enqueue Tdarr scan when Tdarr is actually configured and enabled.
    tdarr_enabled = (
        await db.execute(
            select(ServiceConfig.enabled).where(
                ServiceConfig.service_type == Service.TDARR
            )
        )
    ).scalar_one_or_none()
    if tdarr_enabled:
        tasks_to_run.append(Task.SCAN_TDARR_FLAGGED)

    jobs: dict[str, dict[str, object]] = {}
    for task in tasks_to_run:
        job, queued = await request_task_run(task)
        jobs[task.value] = {
            "queued": queued,
            "job_id": job.id if job is not None else None,
        }

    return {
        "jobs": jobs,
        "tdarr_configured": bool(tdarr_enabled),
    }


@router.get("/duplicates", response_model=PaginatedDuplicatesResponse)
async def get_duplicates(
    _user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=200),
    sort_by: str = Query(
        "reclaimable_size",
        pattern="^(reclaimable_size|total_size|created_at|title)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    media_type: MediaType | None = Query(None),
    search: str | None = Query(None, max_length=200),
    include_resolved: bool = Query(False),
):
    """List duplicate groups with their candidate copies."""
    base = select(DuplicateGroup)
    count_q = select(func.count(DuplicateGroup.id))

    if media_type is not None:
        base = base.where(DuplicateGroup.media_type == media_type)
        count_q = count_q.where(DuplicateGroup.media_type == media_type)

    if not include_resolved:
        base = base.where(DuplicateGroup.resolved.is_(False))
        count_q = count_q.where(DuplicateGroup.resolved.is_(False))

    if search:
        like = f"%{search}%"
        base = base.where(DuplicateGroup.title.ilike(like))
        count_q = count_q.where(DuplicateGroup.title.ilike(like))

    total = (await db.execute(count_q)).scalar_one() or 0

    sort_col = {
        "reclaimable_size": DuplicateGroup.reclaimable_size,
        "total_size": DuplicateGroup.total_size,
        "created_at": DuplicateGroup.created_at,
        "title": DuplicateGroup.title,
    }[sort_by]
    if sort_order == "desc":
        sort_col = sort_col.desc()
    else:
        sort_col = sort_col.asc()

    offset = (page - 1) * per_page
    result = await db.execute(
        base.order_by(sort_col)
        .offset(offset)
        .limit(per_page)
        .options(selectinload(DuplicateGroup.candidates))
    )
    groups = result.scalars().all()

    # total reclaimable across all pages (same filters)
    reclaim_sum_q = select(func.coalesce(func.sum(DuplicateGroup.reclaimable_size), 0))
    if media_type is not None:
        reclaim_sum_q = reclaim_sum_q.where(DuplicateGroup.media_type == media_type)
    if not include_resolved:
        reclaim_sum_q = reclaim_sum_q.where(DuplicateGroup.resolved.is_(False))
    if search:
        like = f"%{search}%"
        reclaim_sum_q = reclaim_sum_q.where(DuplicateGroup.title.ilike(like))
    total_reclaimable = (await db.execute(reclaim_sum_q)).scalar_one() or 0

    # fetch poster URLs for the groups on this page
    movie_ids = [g.movie_id for g in groups if g.movie_id is not None]
    series_ids = [g.series_id for g in groups if g.series_id is not None]
    movie_posters: dict[int, str | None] = {}
    series_posters: dict[int, str | None] = {}
    if movie_ids:
        mres = await db.execute(
            select(Movie.id, Movie.poster_url).where(Movie.id.in_(movie_ids))
        )
        movie_posters = {row[0]: row[1] for row in mres.all()}
    if series_ids:
        sres = await db.execute(
            select(Series.id, Series.poster_url).where(Series.id.in_(series_ids))
        )
        series_posters = {row[0]: row[1] for row in sres.all()}

    items: list[DuplicateGroupEntry] = []
    for g in groups:
        media_id = g.movie_id if g.media_type is MediaType.MOVIE else g.series_id
        poster = (
            movie_posters.get(g.movie_id)
            if g.media_type is MediaType.MOVIE
            else series_posters.get(g.series_id)
        )
        items.append(
            DuplicateGroupEntry(
                id=g.id,
                media_type=g.media_type.value,
                media_id=media_id,
                title=g.title,
                year=g.year,
                poster_url=poster,
                detection_kind=g.detection_kind,
                candidate_count=g.candidate_count,
                total_size=g.total_size,
                reclaimable_size=g.reclaimable_size,
                resolved=g.resolved,
                created_at=to_utc_isoformat(g.created_at) or "",
                candidates=[
                    DuplicateCandidateEntry(
                        id=c.id,
                        service=c.service.value,
                        library_id=c.library_id,
                        library_name=c.library_name,
                        path=c.path,
                        size=c.size,
                        container=c.container,
                        resolution=c.resolution,
                        score=c.score,
                        keep=c.keep,
                    )
                    for c in sorted(
                        g.candidates or [], key=lambda x: x.score, reverse=True
                    )
                ],
            )
        )

    total_pages = (total + per_page - 1) // per_page if total else 0
    return PaginatedDuplicatesResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_reclaimable_bytes=int(total_reclaimable),
    )


@router.post("/duplicates/resolve", response_model=ResolveDuplicatesResponse)
async def resolve_duplicates_route(
    request: ResolveDuplicatesRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    """Delete the non-keep copies in each provided duplicate group via Plex."""
    if not (
        user.role is UserRole.ADMIN or has_permission(user, Permission.MANAGE_RECLAIM)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manage reclaim permission required",
        )
    if not request.group_ids:
        return ResolveDuplicatesResponse(deleted=0, failed=0, groups_resolved=0)

    deleted, failed, resolved = await resolve_duplicate_groups(
        request.group_ids, user_id=user.id
    )
    return ResolveDuplicatesResponse(
        deleted=deleted, failed=failed, groups_resolved=resolved
    )


@router.post("/toggle-duplicate-keep")
async def toggle_duplicate_keep(
    candidate_id: Annotated[int, Query(ge=1)],
    keep: Annotated[bool, Query()],
    user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """Toggle whether a duplicate candidate is the keeper in its group.

    When setting keep=True, any other candidate in the same group is set to False.
    """
    if not (
        user.role is UserRole.ADMIN or has_permission(user, Permission.MANAGE_RECLAIM)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manage reclaim permission required",
        )

    result = await db.execute(
        select(DuplicateCandidate).where(DuplicateCandidate.id == candidate_id)
    )
    cand = result.scalar_one_or_none()
    if cand is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if keep:
        others = await db.execute(
            select(DuplicateCandidate).where(
                DuplicateCandidate.group_id == cand.group_id,
                DuplicateCandidate.id != cand.id,
            )
        )
        for other in others.scalars().all():
            other.keep = False
        cand.keep = True
    else:
        cand.keep = False

    # recompute reclaimable_size for the group
    res_group = await db.execute(
        select(DuplicateGroup)
        .where(DuplicateGroup.id == cand.group_id)
        .options(selectinload(DuplicateGroup.candidates))
    )
    group = res_group.scalar_one()
    keep_size = sum(c.size for c in group.candidates if c.keep)
    total_size = sum(c.size for c in group.candidates)
    group.reclaimable_size = max(0, total_size - keep_size)

    await db.commit()
    return {"ok": True, "reclaimable_size": group.reclaimable_size}
