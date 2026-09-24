from typing import Annotated
import logging
from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool

from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models import Book, Loan
from app.schemas import(LoanReadBook,LoanReadBookMember ,LoanRead)
from app.dependencies import DBsession, CurrentMember, require_librarian, pagination_params



router = APIRouter(prefix="/loans", tags=["loans"])
PaginationDep = Annotated[dict, Depends(pagination_params)]
logger = logging.getLogger(__name__)


@router.get("/me", response_model=list[LoanReadBook])
async def get_loans(member: CurrentMember, db: DBsession):
    loans = (await db.scalars(select(Loan).where(Loan.member == member).options(selectinload(Loan.book)))).all()
    return loans


@router.post("/{loan_id}/return", response_model=LoanRead)
async def return_book(loan_id: int, member: CurrentMember, db: DBsession):
    loan = await db.get(Loan, loan_id, options=[selectinload(Loan.member)])
    if not loan:
        raise HTTPException(status_code=404, detail="Not Found")
    if loan.member != member:
        raise HTTPException(status_code=403, detail="Unuthrized changes")
    loan.returned_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.error(e)
        raise HTTPException(
            status_code=406,
            detail="Couldn't proccess borrow"
        )
    await db.refresh(loan)
    return loan

@router.get("/overdue", response_model= list[LoanReadBookMember], dependencies=[Depends(require_librarian)])
async def get_overdue_loans(db: DBsession):
    stmt = select(Loan).where(Loan.returned_at == None, Loan.due_date < date.today(timezone.utc)).options(selectinload(Loan.book), selectinload(Loan.member))
    loans = (await db.scalars(stmt)).all()
    return loans