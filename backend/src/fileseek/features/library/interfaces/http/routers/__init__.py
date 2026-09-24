"""Library feature 路由聚合。"""

from fastapi import APIRouter

from fileseek.features.library.interfaces.http.routers.file import router as file_router
from fileseek.features.library.interfaces.http.routers.folder import router as folder_router
from fileseek.features.library.interfaces.http.routers.recent import router as recent_router
from fileseek.features.library.interfaces.http.routers.recycle import router as recycle_router

router = APIRouter()
router.include_router(folder_router)
router.include_router(file_router)
router.include_router(recent_router)
router.include_router(recycle_router)

__all__ = ["router"]
