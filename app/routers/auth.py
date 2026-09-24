from typing import Annotated

from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy import select
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

@router.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBsession):
    member = (await db.scalars(select(Member).where(Member.email == form_data.username))).first()
    password_ok = member is not None and await run_in_threadpool(verify_password, form_data.password, member.hashed_password)
    if not password_ok:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": create_access_token(str(member.id)), "token_type": "bearer"} 


@router.get("/me", response_model=MemberRead)
async def read_me(member: CurrentMember):
    return member