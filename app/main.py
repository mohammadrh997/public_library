from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import engine

import logging
from app.routers import auth, books, loans


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("starting  up")
    yield
    print("shutting down")
    await engine.dispose()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


app = FastAPI(title="Library", lifespan=lifespan)


app.include_router(auth.router)
app.include_router(books.router)
app.include_router(loans.router)