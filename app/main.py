import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.exceptions import ResourceNotFound, exp_haneler, resource_not_found_handler
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

app.add_exception_handler(ResourceNotFound, resource_not_found_handler) #type: ignore[arg-type]
app.add_exception_handler(Exception, exp_haneler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myfrontend.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
