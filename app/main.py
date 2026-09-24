from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import engine


from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("starting  up")
    yield
    print("shutting down")
    await engine.dispose()




app = FastAPI(title="Library", lifespan=lifespan)


app.include_router(auth.router)