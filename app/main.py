import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache import create_redis_client
from app.config import settings
from app.database import engine
from app.exceptions import ResourceNotFound, exp_haneler, resource_not_found_handler
from app.rate_limit import limiter
from app.routers import auth, books, health, loans


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis_client(settings.redis_url) if settings.redis_url else None
    yield
    if app.state.redis is not None:
        await app.state.redis.aclose()
    await engine.dispose()


logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


app = FastAPI(title="Public Library Lending API", lifespan=lifespan)
app.state.limiter = limiter


app.include_router(auth.router)
app.include_router(books.router)
app.include_router(loans.router)
app.include_router(health.router)

app.add_exception_handler(ResourceNotFound, resource_not_found_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, exp_haneler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
