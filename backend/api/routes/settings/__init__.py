from fastapi import APIRouter

from .notifications import router as notifications_router
from .services import router as services_router

router = APIRouter(prefix="/api/settings", tags=["settings"])
router.include_router(services_router)
router.include_router(notifications_router)
