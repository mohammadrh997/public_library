import logging
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentMember, DBsession, pagination_params, require_librarian
from app.models import Loan
from app.schemas import LoanRead, LoanReadBook, LoanReadBookMember

router = APIRouter(prefix="/loans", tags=["loans"])
PaginationDep = Annotated[dict, Depends(pagination_params)]
logger = logging.getLogger(__name__)


@router.get("/me", response_model=list[LoanReadBook])
async def get_loans(member: CurrentMember, db: DBsession):
    loans = (
        await db.scalars(select(Loan).where(Loan.member == member).options(selectinload(Loan.book)))
    ).all()
    return loans


@router.post("/{loan_id}/return", response_model=LoanRead)
async def return_book(loan_id: int, member: CurrentMember, db: DBsession):
    loan = await db.get(Loan, loan_id, options=[selectinload(Loan.member)])
    if not loan:
        raise HTTPException(status_code=404, detail="Not Found")
    if loan.member != member:
        raise HTTPException(status_code=403, detail="Unauthorized changes")
    if loan.returned_at:
        raise HTTPException(status_code=409, detail="This book has already been returned")
    loan.returned_at = datetime.now(UTC)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.error(e)
        raise
    await db.refresh(loan)
    return loan


@router.get(
    "/overdue", response_model=list[LoanReadBookMember], dependencies=[Depends(require_librarian)]
)
async def get_overdue_loans(db: DBsession):
    stmt = (
        select(Loan)
        .where(Loan.returned_at == None, Loan.due_date < date.today())
        .options(selectinload(Loan.book), selectinload(Loan.member))
    )
    loans = (await db.scalars(stmt)).all()
    return loans
