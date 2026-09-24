"""Settings feature 路由聚合。"""

from fastapi import APIRouter

from fileseek.features.settings.interfaces.http.routers.nas import router as nas_router
from fileseek.features.settings.interfaces.http.routers.settings import router as settings_router

router = APIRouter()
router.include_router(settings_router)
router.include_router(nas_router)

__all__ = ["router"]
