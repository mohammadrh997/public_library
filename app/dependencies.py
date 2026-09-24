from typing import Annotated
from collections.abc import AsyncGenerator


from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.security import verify_token
from app.models import Member


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


DBsession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_member(token: Annotated[str, Depends(oauth2_scheme)], db: DBsession) -> Member:
    member_id = verify_token(token)
    #check for User Return None or Return non integer value
    try:
        member_id = int(member_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    member = await db.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=401, detail="Member no longer exists")
    return member


CurrentMember = Annotated[Member, Depends(get_current_member)]