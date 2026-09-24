from typing import Annotated
import logging

from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models import Book, Loan
from app.schemas import(BookRead, BookCreate, BookUpdate)
from app.dependencies import DBsession, CurrentMember, require_librarian, pagination_params



router = APIRouter(prefix="/books", tags=["books"])
PaginationDep = Annotated[dict, Depends(pagination_params)]
logger = logging.getLogger(__name__)


async def fetch_book(book_id: int, db: AsyncSession):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Not Found")
    return book


@router.get("", response_model=list[BookRead])
async def get_books(db: DBsession, pagation: PaginationDep, search: None | str = None):
    stmt = select(Book).order_by(Book.id)
    if search:
        stmt = stmt.where(Book.author == search)
    stmt = stmt.offset(pagation.get("skip")).limit(pagation.get("limit"))
    books = (await db.scalars(stmt)).all()
    if not books:
        raise HTTPException(status_code=404, detail="Not Found")
    return books

@router.get("/{book_id}", response_model= BookRead)
async def get_book(book_id: int, db: DBsession):
    book = await fetch_book(book_id, db)
    return book


@router.post("", response_model= BookRead, status_code=status.HTTP_201_CREATED, dependencies=[(Depends(require_librarian))])
async def add_book(payload: BookCreate, db: DBsession):
    book = Book(**payload.model_dump())
    db.add(book)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="the ISBN already exists",
        )
    await db.refresh(book)
    return book


@router.patch("/{book_id}", response_model=BookRead, dependencies=[(Depends(require_librarian))])
async def patch_book(book_id: int, payload: BookUpdate, db: DBsession):
    book = await fetch_book(book_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.error(e)
        raise HTTPException(
            status_code=409,
            detail="the ISBN already exists",
        )
    await db.refresh(book)
    return book

@router.delete("/{book_id}", dependencies=[(Depends(require_librarian))], status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db: DBsession):
    book = await fetch_book(book_id, db)
    await db.delete(book)
    await db.commit()
