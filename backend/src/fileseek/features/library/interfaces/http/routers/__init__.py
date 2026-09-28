"""Library feature 路由聚合。"""

from fastapi import APIRouter

from fileseek.features.library.interfaces.http.routers.file import router as file_router
from fileseek.features.library.interfaces.http.routers.folder import router as folder_router
from fileseek.features.library.interfaces.http.routers.tag import router as tag_router

router = APIRouter(prefix="/library",tags=["Library"])
router.include_router(folder_router)
router.include_router(file_router)
router.include_router(tag_router)

__all__ = ["router"]
