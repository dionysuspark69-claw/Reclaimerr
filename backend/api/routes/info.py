from fastapi import APIRouter

from backend.core import __version__

router = APIRouter(prefix="/api/info", tags=["info"])


@router.get("/version")
async def get_version() -> dict[str, str]:
    """Get application version."""
    return {
        "version": str(__version__),
        "program": __version__.program_name,
        "url": __version__.program_url,
    }
