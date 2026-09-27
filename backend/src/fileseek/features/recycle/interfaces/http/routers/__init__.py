from __future__ import annotations

from fastapi import APIRouter

from fileseek.features.recycle.interfaces.http.routers.recycle import router as recycle_router

router = APIRouter()
router.include_router(recycle_router, tags=["Recycle"])
