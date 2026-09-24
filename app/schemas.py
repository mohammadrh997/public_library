from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date


class MemberBase(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=20)


class MemberCreate(MemberBase):
    password: str = Field(min_length=8, max_length=40)


class MemberUpdate(BaseModel):
    email: Optional[EmailStr] = Field(default= None)
    name: Optional[str] = Field(default= None, min_length=1, max_length=20)
    password: Optional[str] = Field(default= None, min_length=8, max_length=40)


class MemberRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    email: EmailStr
    name: str
    is_librarian: bool






class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=50)
    author: str = Field(min_length=1, max_length=50)
    isbn: str = Field(min_length=10, max_length=20)
    total_copies: int = Field(ge=0)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = Field(min_length=1, max_length=50, default=None)
    author: Optional[str] = Field(min_length=1, max_length=50, default=None)
    isbn: Optional[str] = Field(min_length=10, max_length=20, default=None)
    total_copies: Optional[int] = Field(ge=0, default=None)


class BookRead(BookBase):
    model_config = {"from_attributes": True}

    id: int






class LoanBase(BaseModel):
    book_id: int
    member_id: int
    due_date: date
    returned_at : date | None = None
    


class LoanCreate(LoanBase):
    pass


class LoanUpdate(BaseModel):
    book_id: Optional[int] = None 
    member_id: Optional[int] = None
    due_date: Optional[date] = None
    returned_at : date | None = None


class LoanRead(LoanBase):
    model_config = {"from_attributes": True}

    id: int
    borrowed_at: date

class LoanReadBook(LoanRead):
    model_config = {"from_attributes": True}

    book: "BookRead"

class LoanReadBookMember(LoanReadBook):
    model_config = {"from_attributes": True}

    member: "MemberRead"