"""API router'ları — tek api_router altında toplanır."""

from fastapi import APIRouter

from . import (
    abandoned,
    billing,
    chapters,
    chat,
    courses,
    coverage,
    errors,
    essay_draft,
    exams,
    exports,
    feed,
    flashcards,
    heatmap,
    indexing,
    materials,
    media,
    next_action,
    notes,
    overall,
    quiz_review,
    recall,
    retention_progress,
    saved_questions,
    slides,
    study_sessions,
    terms,
    v2_tools,
)
from . import settings as settings_router

api_router = APIRouter()
api_router.include_router(terms.router)
api_router.include_router(courses.router)
api_router.include_router(errors.router)
api_router.include_router(exams.router)
api_router.include_router(heatmap.router)
api_router.include_router(coverage.router)
api_router.include_router(materials.router)
api_router.include_router(media.router)
api_router.include_router(feed.router)
api_router.include_router(next_action.router)
api_router.include_router(quiz_review.router)
api_router.include_router(abandoned.router)
api_router.include_router(chapters.router)
api_router.include_router(slides.router)
api_router.include_router(indexing.router)
api_router.include_router(notes.router)
api_router.include_router(chat.router)
api_router.include_router(flashcards.router)
api_router.include_router(overall.router)
api_router.include_router(exports.router)
api_router.include_router(v2_tools.router)
api_router.include_router(settings_router.router)
api_router.include_router(billing.router)
api_router.include_router(study_sessions.router)
api_router.include_router(essay_draft.router)
api_router.include_router(retention_progress.router)
api_router.include_router(recall.router)
api_router.include_router(saved_questions.router)
