from fastapi import APIRouter

from app.api.v1 import (
    admin_stats,
    auth,
    chat,
    citations,
    documents,
    feedback,
    knowledge_bases,
    sessions,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(sessions.router)
api_router.include_router(chat.router)
api_router.include_router(citations.router)
api_router.include_router(feedback.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(knowledge_bases.admin_router)
api_router.include_router(documents.router)
api_router.include_router(admin_stats.router)
