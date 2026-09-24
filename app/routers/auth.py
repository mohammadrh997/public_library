from fastapi import APIRouter, status, HTTPException
from fastapi.concurrency import run_in_threadpool

from sqlalchemy.exc import IntegrityError

from app.models import Member
from app.security import hash_password, verify_password, create_access_token
from app.schemas import(MemberCreate, MemberRead, MemberUpdate)
from app.dependencies import DBsession, CurrentMember



router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
async def create_member(payload: MemberCreate, db: DBsession):
    hashed_passowrd = await run_in_threadpool(hash_password,payload.password)
    member = Member(email= payload.email, name=payload.name, hashed_password=hashed_passowrd)
    db.add(member)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )
    await db.refresh(member)
    return member