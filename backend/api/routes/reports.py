from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.utils.datetime_utils import to_utc_isoformat
from backend.database import get_db
from backend.database.models import ReclaimEvent, User
from backend.enums import ReclaimSource

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/reclaim")
async def get_reclaim_report(
    _user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    recent_limit: int = Query(25, ge=1, le=200),
) -> dict[str, Any]:
    """Aggregate reclaim statistics for the Reports tab.

    Returns totals (all-time / 30d / 7d), a breakdown by source, a 12-month
    bytes-reclaimed histogram, and the most recent N events.
    """
    now = datetime.now(timezone.utc)
    window_30d = now - timedelta(days=30)
    window_7d = now - timedelta(days=7)

    total_bytes = (
        await db.execute(select(func.coalesce(func.sum(ReclaimEvent.bytes_reclaimed), 0)))
    ).scalar_one()
    total_events = (
        await db.execute(select(func.count(ReclaimEvent.id)))
    ).scalar_one()
    bytes_30d = (
        await db.execute(
            select(func.coalesce(func.sum(ReclaimEvent.bytes_reclaimed), 0)).where(
                ReclaimEvent.created_at >= window_30d
            )
        )
    ).scalar_one()
    bytes_7d = (
        await db.execute(
            select(func.coalesce(func.sum(ReclaimEvent.bytes_reclaimed), 0)).where(
                ReclaimEvent.created_at >= window_7d
            )
        )
    ).scalar_one()

    # Breakdown by source.
    by_source_rows = (
        await db.execute(
            select(
                ReclaimEvent.source,
                func.count(ReclaimEvent.id),
                func.coalesce(func.sum(ReclaimEvent.bytes_reclaimed), 0),
            ).group_by(ReclaimEvent.source)
        )
    ).all()

    # Initialize with zeros so the frontend can rely on every source being present.
    by_source: dict[str, dict[str, int]] = {
        src.value: {"count": 0, "bytes": 0} for src in ReclaimSource
    }
    for src, count, bytes_sum in by_source_rows:
        by_source[src.value if hasattr(src, "value") else str(src)] = {
            "count": int(count or 0),
            "bytes": int(bytes_sum or 0),
        }

    # 12-month histogram (inclusive of current month).
    histogram: list[dict[str, Any]] = []
    for i in range(11, -1, -1):
        # Compute the first day of the month that's `i` months before the
        # first of this month. Simple walk avoids calendar math edge cases.
        ref = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year = ref.year
        month = ref.month - i
        while month <= 0:
            month += 12
            year -= 1
        start = ref.replace(year=year, month=month)
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        end = ref.replace(year=next_year, month=next_month)

        bucket_bytes = (
            await db.execute(
                select(func.coalesce(func.sum(ReclaimEvent.bytes_reclaimed), 0)).where(
                    ReclaimEvent.created_at >= start,
                    ReclaimEvent.created_at < end,
                )
            )
        ).scalar_one()
        histogram.append(
            {
                "month": start.strftime("%Y-%m"),
                "bytes": int(bucket_bytes or 0),
            }
        )

    # Recent events join users table for display name.
    recent_rows = (
        await db.execute(
            select(ReclaimEvent, User)
            .outerjoin(User, ReclaimEvent.triggered_by_user_id == User.id)
            .order_by(ReclaimEvent.created_at.desc(), ReclaimEvent.id.desc())
            .limit(recent_limit)
        )
    ).all()

    recent = [
        {
            "id": event.id,
            "source": event.source,
            "media_type": event.media_type,
            "media_title": event.media_title,
            "media_year": event.media_year,
            "bytes_reclaimed": event.bytes_reclaimed,
            "triggered_by_username": (
                user.display_name or user.username if user is not None else None
            ),
            "notes": event.notes,
            "created_at": to_utc_isoformat(event.created_at),
        }
        for event, user in recent_rows
    ]

    return {
        "total_bytes": int(total_bytes or 0),
        "total_events": int(total_events or 0),
        "bytes_last_30d": int(bytes_30d or 0),
        "bytes_last_7d": int(bytes_7d or 0),
        "by_source": by_source,
        "monthly_histogram": histogram,
        "recent": recent,
    }
