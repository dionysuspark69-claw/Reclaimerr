from fastapi import APIRouter

from .info import router as info_router

router = APIRouter(prefix="/api/info", tags=["info"])
router.include_router(info_router)
