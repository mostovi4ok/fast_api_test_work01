from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, Relationship, declared_attr, mapped_column, relationship


class Base(DeclarativeBase):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)


class Account(Base):
    __tablename__ = "account"

    name: Mapped[str] = mapped_column(String(30))


class Catalog(Base):
    __abstract__ = True

    @declared_attr
    def money(self) -> Relationship[Money]:
        return relationship(
            "Money",
            cascade="all, delete",
            passive_deletes=True,
        )


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
    serial_namber: Mapped[str] = mapped_column(String(30))
    user: Mapped[int] = mapped_column(ForeignKey(Account.id), nullable=True)
    type_money: Mapped[int] = mapped_column(ForeignKey(TypeMoney.id, ondelete="CASCADE"), nullable=False)
    currency: Mapped[int] = mapped_column(ForeignKey(Currency.id, ondelete="CASCADE"), nullable=False)
    mint: Mapped[int] = mapped_column(ForeignKey(Mint.id, ondelete="CASCADE"), nullable=False)
    issuing_state: Mapped[int] = mapped_column(ForeignKey(IssuingState.id, ondelete="CASCADE"), nullable=False)
