import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.dependencies import DBsession

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: DBsession, response: Response):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}
