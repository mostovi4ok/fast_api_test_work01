from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, column
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from .types import StatusTransfer


class Base(DeclarativeBase):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Index, ...]:
        return (Index(f"{cls.__tablename__}_not_deleted_at", "id", postgresql_where=(column("deleted_at") != None)),)


class Account(Base):
    __tablename__ = "account"

    name: Mapped[str] = mapped_column(String(30), unique=True)
    is_admin: Mapped[bool] = mapped_column(default=False)


class Catalog(Base):
    __abstract__ = True


class TypeMoney(Catalog):
    __tablename__ = "type_money"


class Currency(Catalog):
    __tablename__ = "currency"


class Mint(Catalog):
    __tablename__ = "mint"


class IssuingState(Catalog):
    __tablename__ = "issuing_state"


class Money(Base):
    __tablename__ = "money"

    description: Mapped[str] = mapped_column(String(100))
    nominal_price: Mapped[int]
    release_year: Mapped[str] = mapped_column(String(4))
    serial_number: Mapped[str] = mapped_column(String(30))
    user: Mapped[int] = mapped_column(ForeignKey(Account.id), nullable=False)
    type_money: Mapped[int] = mapped_column(ForeignKey(TypeMoney.id), nullable=False)
    currency: Mapped[int] = mapped_column(ForeignKey(Currency.id), nullable=False)
    mint: Mapped[int] = mapped_column(ForeignKey(Mint.id), nullable=False)
    issuing_state: Mapped[int] = mapped_column(ForeignKey(IssuingState.id), nullable=False)


initial_status = column("status") == StatusTransfer.initial.value


class Transfer(Base):
    __tablename__ = "transfer"

    source: Mapped[int] = mapped_column(ForeignKey(Account.id), nullable=False)
    destination: Mapped[int] = mapped_column(ForeignKey(Account.id), nullable=False)
    creater: Mapped[int] = mapped_column(ForeignKey(Account.id), nullable=False)
    created_at: Mapped[datetime]
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    comment: Mapped[str] = mapped_column(String(100))
    money: Mapped[int] = mapped_column(ForeignKey(Money.id), nullable=False)
    status: Mapped[StatusTransfer]

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Index, ...]:
        return (
            Index("activ_destination", "destination", postgresql_where=(initial_status)),
            Index("activ_transfer", "id", postgresql_where=(initial_status)),
            Index("uniq_transfer", "source", "money", unique=True, postgresql_where=(initial_status)),
        ) + super().__table_args__
