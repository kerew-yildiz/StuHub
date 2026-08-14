"""API router'ları — tek api_router altında toplanır."""

from fastapi import APIRouter

from . import settings as settings_router
from . import terms

api_router = APIRouter()
api_router.include_router(terms.router)
api_router.include_router(settings_router.router)
