from typing import Annotated

from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Book, Loan
from app.schemas import(BookRead, BookCreate, BookUpdate)
from app.dependencies import DBsession, CurrentMember, require_librarian, pagination_params



router = APIRouter(prefix="/books", tags=["books"])
PaginationDep = Annotated[dict, Depends(pagination_params)]

@router.get("/books", response_model=list[BookRead])
async def get_books(db: DBsession, pagation: PaginationDep, search: None | str = None):
    stmt = select(Book).order_by(Book.id)
    if search:
        stmt = stmt.where(Book.author == search)
    stmt = stmt.offset(pagation.get("skip")).limit(pagation.get("limit"))
    books = (await db.scalars(stmt)).all()
    if not books:
        raise HTTPException(status_code=404, detail="Not Found")
    return books