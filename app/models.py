from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, func, false
from datetime import date


from app.database import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    hashed_password: Mapped[str]
    is_librarian: Mapped[bool] = mapped_column(server_default=false())
    joined_date: Mapped[date] = mapped_column(server_default=func.current_date())
    loans: Mapped[list["Loan"]] = relationship(back_populates="member")



class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    author: Mapped[str]
    isbn: Mapped[str] = mapped_column(unique=True)
    total_copies: Mapped[int]
    loans: Mapped[list["Loan"]] = relationship(back_populates="book")


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    book: Mapped["Book"] = relationship(back_populates="loans")
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    member: Mapped["Member"] = relationship(back_populates="loans")
    borrowed_at: Mapped[date] = mapped_column(server_default=func.current_date())
    due_date: Mapped[date]
    returned_at : Mapped[date | None] = mapped_column(nullable=True)
