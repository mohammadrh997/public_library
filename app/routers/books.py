from typing import Annotated
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, status, HTTPException, Depends, BackgroundTasks
from fastapi.concurrency import run_in_threadpool

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models import Book, Loan
from app.exceptions import ResourceNotFound
from app.schemas import(BookRead, BookCreate, BookUpdate, LoanRead)
from app.dependencies import DBsession, CurrentMember, require_librarian, pagination_params



router = APIRouter(prefix="/books", tags=["books"])
PaginationDep = Annotated[dict, Depends(pagination_params)]
logger = logging.getLogger(__name__)


async def fetch_book(book_id: int, db: AsyncSession) -> Book:
    book = await db.get(Book, book_id)
    if not book:
        raise ResourceNotFound("book", book_id)
    return book

def append_log(book: Book):
    with open("lending_log.txt", "a") as file:
        file.write(f"Book number {book.id} was sccuessfully borrow at {datetime.now(timezone.utc)}\n")


@router.get("", response_model=list[BookRead])
async def get_books(db: DBsession, pagation: PaginationDep, search: None | str = None):
    stmt = select(Book).order_by(Book.id)
    if search:
        stmt = stmt.where(Book.author == search)
    stmt = stmt.offset(pagation.get("skip")).limit(pagation.get("limit"))
    books = (await db.scalars(stmt)).all()
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
    try:
        await db.delete(book)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete this book because it has loan records.",
        )



@router.post("/{book_id}/borrow", response_model=LoanRead)
async def borrow_book(book_id: int, member: CurrentMember, db: DBsession, backgrounder: BackgroundTasks):
    book = await fetch_book(book_id, db)
    # if every copy is already on loan
    stmt = select(func.count(Loan.id)).where(and_(Loan.book == book, Loan.returned_at == None))
    active_loans = await db.scalar(stmt)
    if book.total_copies <= active_loans:
        raise HTTPException(
                    status_code=422,
                    detail="The book have no avaliable copies",
                )
    
    # if this member already has an unreturned loan of this book
    stmt = select(Loan).where(Loan.book == book, Loan.member == member, Loan.returned_at == None)
    loans = (await db.scalars(stmt)).all()
    if loans:
        raise HTTPException(
                status_code=422,
                detail="You already have copy of this book",
            )
    due_date = datetime.now(timezone.utc) + timedelta(days= 14)
    loan = Loan(book=book, member=member, due_date=due_date)
    db.add(loan)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.error(e)
        raise HTTPException(
                status_code=406,
                detail="Couldn't proccess borrow",
            )
    backgrounder.add_task(append_log, book)
    await db.refresh(loan)
    return loan