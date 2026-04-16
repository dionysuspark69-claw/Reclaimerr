from __future__ import annotations

from datetime import datetime, timezone

import niquests
from niquests.exceptions import ReadTimeout
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.core.logger import LOG
from backend.core.utils.request import should_retry_on_status
from backend.models.services.tautulli import TautulliWatchSummary


class TautulliService:
    """Tautulli analytics companion for Plex.

    Provides richer per-item watch history that supplements Plex's own
    built-in viewCount / lastViewedAt counters.
    """

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = niquests.AsyncSession(timeout=300)

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=(
            retry_if_exception_type((ConnectionError, TimeoutError, ReadTimeout))
            | retry_if_exception(should_retry_on_status)
        ),
    )
    async def _make_request(
        self, cmd: str, extra_params: dict | None = None
    ) -> dict | list:
        """Make an authenticated request to the Tautulli API v2."""
        params: dict = {"apikey": self.api_key, "cmd": cmd, "apiVersion": "2"}
        if extra_params:
            params.update(extra_params)
        response = await self.session.get(f"{self.base_url}/api/v2", params=params)
        response.raise_for_status()
        data = response.json()
        result = data.get("response", {})
        if result.get("result") != "success":
            raise ValueError(
                f"Tautulli API error for cmd={cmd!r}: {result.get('message', 'unknown')}"
            )
        return result.get("data", {})

    async def health(self) -> bool:
        """Check that the Tautulli server is reachable and the API key is valid."""
        try:
            await self._make_request("get_server_info")
            return True
        except Exception:
            return False

    async def get_watch_history(self, length: int = 10000) -> list[dict]:
        """Fetch the flat watch history from Tautulli.

        Args:
            length: Maximum number of records to retrieve.

        Returns:
            List of raw history record dicts.
        """
        try:
            data = await self._make_request(
                "get_history",
                {
                    "length": str(length),
                    "order_column": "date",
                    "order_dir": "desc",
                },
            )
            # response structure: {"data": [...], "recordsFiltered": N, "recordsTotal": N}
            if isinstance(data, dict):
                return data.get("data", [])
            return []
        except Exception as e:
            LOG.error(f"Failed to fetch Tautulli watch history: {e}")
            return []

    async def get_watch_summaries(self) -> dict[str, TautulliWatchSummary]:
        """Aggregate watch history into per-Plex-ratingKey summaries.

        For movies, the summary is keyed by the movie's ``rating_key``.
        For TV episodes, the summary is keyed by ``grandparent_rating_key``
        (the show's ratingKey), so watch counts accumulate at the series level.

        Only plays where ``percent_complete >= 50`` are counted as a watch,
        mirroring Plex's own "played" threshold.

        Returns:
            Dict mapping Plex ratingKey -> TautulliWatchSummary.
        """
        history = await self.get_watch_history()

        counts: dict[str, int] = {}
        last_dates: dict[str, datetime | None] = {}

        for entry in history:
            percent_complete = entry.get("percent_complete", 0) or 0
            if float(percent_complete) < 50:
                continue

            gp_key = entry.get("grandparent_rating_key")
            rk = entry.get("rating_key", "")
            # use grandparent (show) key for episodes; fall back to item key for movies
            effective_key = (
                str(gp_key) if gp_key and str(gp_key) not in ("", "0") else str(rk)
            )
            if not effective_key:
                continue

            counts[effective_key] = counts.get(effective_key, 0) + 1

            raw_date = entry.get("date")
            if raw_date:
                try:
                    lva = datetime.fromtimestamp(int(raw_date), tz=timezone.utc)
                    prev = last_dates.get(effective_key)
                    if prev is None or lva > prev:
                        last_dates[effective_key] = lva
                except (TypeError, ValueError, OSError):
                    pass
            elif effective_key not in last_dates:
                last_dates[effective_key] = None

        return {
            key: TautulliWatchSummary(
                rating_key=key,
                view_count=counts[key],
                last_viewed_at=last_dates.get(key),
            )
            for key in counts
        }

    @staticmethod
    async def test_service(url: str, api_key: str) -> bool:
        """Test a Tautulli connection without full initialisation.

        Args:
            url: Tautulli base URL (e.g. ``http://localhost:8181``).
            api_key: Tautulli API key.

        Returns:
            True if the server responded successfully.
        """
        async with niquests.AsyncSession() as session:
            response = await session.get(
                f"{url.rstrip('/')}/api/v2",
                params={"apikey": api_key, "cmd": "get_server_info", "apiVersion": "2"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("response", {}).get("result") != "success":
                raise ValueError("Tautulli API returned a non-success response")
            return True
