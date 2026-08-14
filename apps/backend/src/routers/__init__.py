"""API router'ları — tek api_router altında toplanır."""

from fastapi import APIRouter

from . import (
    chapters,
    chat,
    courses,
    exports,
    indexing,
    materials,
    notes,
    overall,
    quizzes,
    slides,
    terms,
)
from . import settings as settings_router

api_router = APIRouter()
api_router.include_router(terms.router)
api_router.include_router(courses.router)
api_router.include_router(materials.router)
api_router.include_router(chapters.router)
api_router.include_router(slides.router)
api_router.include_router(indexing.router)
api_router.include_router(notes.router)
api_router.include_router(chat.router)
api_router.include_router(quizzes.router)
api_router.include_router(overall.router)
api_router.include_router(exports.router)
api_router.include_router(settings_router.router)
