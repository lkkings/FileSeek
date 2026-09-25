from __future__ import annotations

from fastapi import APIRouter

from fileseek.features.recent.interfaces.http.routers.recent import router as recent_router

router = APIRouter()
router.include_router(recent_router, prefix="/recent", tags=["Recent"])
