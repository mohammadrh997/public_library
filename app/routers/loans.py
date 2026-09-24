from typing import Annotated
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool

from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models import Book, Loan
from app.schemas import(LoanReadBook, LoanRead)
from app.dependencies import DBsession, CurrentMember, require_librarian, pagination_params



router = APIRouter(prefix="/loans", tags=["loans"])
PaginationDep = Annotated[dict, Depends(pagination_params)]
logger = logging.getLogger(__name__)


@router.get("/me", response_model=list[LoanReadBook])
async def get_loans(member: CurrentMember, db: DBsession):
    loans = (await db.scalars(select(Loan).where(Loan.member == member).options(selectinload(Loan.book)))).all()
    if not loans:
        raise HTTPException(status_code=404, detail="Not Found")
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