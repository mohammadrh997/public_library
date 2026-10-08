import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import (
    BOOK_LIST_TTL_SECONDS,
    Cache,
    book_list_key,
    cache_get,
    cache_set,
    invalidate_book_lists,
)
from app.dependencies import CurrentMember, DBsession, pagination_params, require_librarian
from app.exceptions import ResourceNotFound
from app.models import Book, Loan
from app.schemas import BookCreate, BookRead, BookUpdate, LoanRead

router = APIRouter(prefix="/books", tags=["books"])
PaginationDep = Annotated[dict, Depends(pagination_params)]
logger = logging.getLogger(__name__)


async def fetch_book(book_id: int, db: AsyncSession) -> Book:
    book = await db.get(Book, book_id)
    if not book:
        raise ResourceNotFound("book", book_id)
    return book


def append_log(book: Book):
    logger.info("Book %s was borrowed", book.id)


@router.get("", response_model=list[BookRead])
async def get_books(
    db: DBsession, cache: Cache, pagination: PaginationDep, author: None | str = None
):
    skip, limit = pagination["skip"], pagination["limit"]
    key = book_list_key(skip, limit, author)
    cached = await cache_get(cache, key)
    if cached is not None:
        return cached
    stmt = select(Book).order_by(Book.id)
    if author:
        stmt = stmt.where(Book.author == author)
    stmt = stmt.offset(skip).limit(limit)
    books = (await db.scalars(stmt)).all()

    result = [BookRead.model_validate(b).model_dump(mode="json") for b in books]
    await cache_set(cache, key, result, ttl=BOOK_LIST_TTL_SECONDS)
    return result


@router.get("/{book_id}", response_model=BookRead)
async def get_book(book_id: int, db: DBsession, request: Request, response: Response):
    book = await fetch_book(book_id, db)
    body = BookRead.model_validate(book).model_dump(mode="json")
    etag = '"' + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=60"}
        )
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=60"
    return body


@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[(Depends(require_librarian))],
)
async def add_book(payload: BookCreate, db: DBsession, cache: Cache):
    book = Book(**payload.model_dump())
    db.add(book)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="the ISBN already exists",
        ) from exc
    await db.refresh(book)
    await invalidate_book_lists(cache)
    return book


@router.patch("/{book_id}", response_model=BookRead, dependencies=[(Depends(require_librarian))])
async def patch_book(book_id: int, payload: BookUpdate, db: DBsession, cache: Cache):
    book = await fetch_book(book_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="the ISBN already exists",
        ) from exc
    await db.refresh(book)
    await invalidate_book_lists(cache)
    return book


@router.delete(
    "/{book_id}",
    dependencies=[(Depends(require_librarian))],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_book(book_id: int, db: DBsession, cache: Cache):
    book = await fetch_book(book_id, db)
    try:
        await db.delete(book)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete this book because it has loan records.",
        ) from exc
    await invalidate_book_lists(cache)


@router.post("/{book_id}/borrow", response_model=LoanRead, status_code=status.HTTP_201_CREATED)
async def borrow_book(
    book_id: int, member: CurrentMember, db: DBsession, backgrounder: BackgroundTasks
):
    book = await fetch_book(book_id, db)

    # if this member already has an unreturned loan of this book
    stmt = select(Loan).where(Loan.book == book, Loan.member == member, Loan.returned_at.is_(None))
    loans = (await db.scalars(stmt)).all()
    if loans:
        raise HTTPException(
            status_code=409,
            detail="You already have a copy of this book",
        )
    # if every copy is already on loan
    stmt2 = select(func.count(Loan.id)).where(and_(Loan.book == book, Loan.returned_at.is_(None)))
    active_loans = (await db.execute(stmt2)).scalar_one()
    if book.total_copies <= active_loans:
        raise HTTPException(
            status_code=409,
            detail="The book has no available copies",
        )
    due_date = datetime.now(UTC) + timedelta(days=14)
    loan = Loan(book=book, member=member, due_date=due_date)
    db.add(loan)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.error(e)
        raise
    backgrounder.add_task(append_log, book)
    await db.refresh(loan)
    return loan
