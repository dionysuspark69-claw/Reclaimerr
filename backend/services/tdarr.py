from __future__ import annotations

import niquests
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.core.utils.request import should_retry_on_status
from backend.models.services.tdarr import TdarrFlaggedFile


def _parse_tdarr_file(doc: dict) -> TdarrFlaggedFile:
    """Convert a Tdarr file document into our internal representation."""
    file_size = doc.get("file_size") or doc.get("fileSize") or 0
    if isinstance(file_size, str):
        try:
            file_size = int(file_size)
        except ValueError:
            file_size = 0

    new_size = doc.get("newSize") or doc.get("file_size_new")
    estimated_savings = 0
    if isinstance(new_size, (int, float)) and isinstance(file_size, int):
        if new_size and new_size < file_size:
            estimated_savings = int(file_size - new_size)

    reason_bits: list[str] = []
    if doc.get("TranscodeDecisionMaker"):
        reason_bits.append(str(doc["TranscodeDecisionMaker"]))
    if doc.get("processingStatus"):
        reason_bits.append(str(doc["processingStatus"]))
    reason = " | ".join(reason_bits) or "Tdarr flagged"

    return TdarrFlaggedFile(
        id=str(doc.get("_id") or doc.get("id") or ""),
        file_path=str(doc.get("file") or doc.get("file_path") or ""),
        library_id=doc.get("DB") or doc.get("libraryId"),
        library_name=doc.get("library") or doc.get("libraryName"),
        container=doc.get("container"),
        video_codec=doc.get("video_codec_name") or doc.get("videoCodec"),
        resolution=doc.get("video_resolution") or doc.get("resolution"),
        file_size=int(file_size) if isinstance(file_size, (int, float)) else 0,
        estimated_savings=estimated_savings,
        reason=reason,
        raw=doc,
    )


class TdarrClient:
    """Minimal Tdarr API client.

    Tdarr exposes a REST-ish API on its server. We only need to:
      1. Health-check.
      2. Pull files Tdarr has classified as needing transcode (oversized,
         wrong codec, etc.) so we can surface them as reclaim candidates.
    """

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = niquests.AsyncSession()
        # Tdarr accepts the API key either as a header or as a query param,
        # depending on version. Set both for maximum compatibility.
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            }
        )

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=(
            retry_if_exception_type((ConnectionError, TimeoutError))
            | retry_if_exception(should_retry_on_status)
        ),
    )
    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> tuple[int, dict | list | None]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.session.request(method, url, **kwargs)
        response.raise_for_status()

        status_code = response.status_code
        if not status_code:
            raise ValueError("Status code should not be None")

        if response.content:
            try:
                return status_code, response.json()
            except Exception:
                return status_code, None
        return status_code, None

    async def health(self) -> bool:
        """Server reachable + API responding."""
        try:
            await self._make_request("GET", "api/v2/status")
            return True
        except Exception:
            try:
                # Older Tdarr exposes /api/v2/cruddb. Try that as a fallback.
                await self._make_request(
                    "POST",
                    "api/v2/cruddb",
                    json={"data": {"collection": "StatisticsJSONDB", "mode": "getAll"}},
                )
                return True
            except Exception:
                return False

    async def get_flagged_files(self) -> list[TdarrFlaggedFile]:
        """Return files Tdarr has flagged as needing transcode.

        We query the FileJSONDB and keep rows whose TranscodeDecisionMaker
        indicates a transcode is needed.
        """
        try:
            status, data = await self._make_request(
                "POST",
                "api/v2/cruddb",
                json={"data": {"collection": "FileJSONDB", "mode": "getAll"}},
            )
        except Exception:
            return []

        if not isinstance(data, list):
            return []

        results: list[TdarrFlaggedFile] = []
        for doc in data:
            if not isinstance(doc, dict):
                continue
            decision = (doc.get("TranscodeDecisionMaker") or "").lower()
            # Tdarr uses "transcode" / "transcode success" / "queued" etc.
            # Anything other than "not required" / "ignored" / "" is interesting.
            if decision in ("", "not required", "ignored", "skipped"):
                continue
            results.append(_parse_tdarr_file(doc))
        return results

    @staticmethod
    async def test_service(url: str, api_key: str) -> bool:
        """Test Tdarr service connection without full initialization."""
        async with niquests.AsyncSession() as session:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            response = await session.get(
                f"{url.rstrip('/')}/api/v2/status",
                headers=headers,
            )
            response.raise_for_status()
            if response.status_code == 200:
                return True
            raise ValueError(f"Unexpected status code: {response.status_code}")
