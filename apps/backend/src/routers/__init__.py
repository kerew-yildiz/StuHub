"""API router'ları — tek api_router altında toplanır."""

from fastapi import APIRouter

from . import chapters, courses, materials, terms
from . import settings as settings_router

api_router = APIRouter()
api_router.include_router(terms.router)
api_router.include_router(courses.router)
api_router.include_router(materials.router)
api_router.include_router(chapters.router)
api_router.include_router(settings_router.router)
