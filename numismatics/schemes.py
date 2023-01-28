from datetime import datetime
from typing import Literal

from pydantic import BaseModel, validator

from .types import StatusTransfer


class BaseScheme(BaseModel):
    pass


class ModelScheme(BaseScheme):
    id: int

    class Config:
        orm_mode = True


class Catalog(ModelScheme):
    pass


class NewAccount(BaseModel):
    name: str
    is_admin: bool = False

    @validator("name")
    def name_length(cls, name) -> str:
        if len(name) > 30:
            raise ValueError("too big")

        return name


class Account(ModelScheme):
    name: str
    is_admin: bool = False


class Money(ModelScheme):
    description: str
    nominal_price: int
    release_year: str
    serial_namber: str
    type_money: int
    currency: int
    mint: int
    issuing_state: int
    user: int


class CreateMoney(BaseScheme):
    description: str
    nominal_price: int
    release_year: str
    serial_namber: str
    type_money: int
    currency: int
    mint: int
    issuing_state: int


class CollectionMoney(ModelScheme):
    name: str
    description: str
    user: int
    money: int


class AddCollectionMoney(BaseScheme):
    name: str
    description: str
    user: int
    money: int


class Transfer(ModelScheme):
    source: int
    destination: int
    creater: int
    created_at: datetime
    closed_at: datetime | None = None
    comment: str
    money: int
    status: StatusTransfer


class CreateTransfer(BaseScheme):
    source: int
    destination: int
    comment: str
    money: int


class Filtration(BaseScheme):
    id: int | None = None
    description: str | None = None
    nominal_price: int | None = None
    release_year: str | None = None
    serial_namber: str | None = None
    type_money: int | None = None
    currency: int | None = None
    mint: int | None = None
    issuing_state: int | None = None


AscDesc = Literal["+", "-"]


class Ordering(BaseScheme):
    id: AscDesc | None = None
    description: AscDesc | None = None
    nominal_price: AscDesc | None = None
    release_year: AscDesc | None = None
    serial_namber: AscDesc | None = None
    type_money: AscDesc | None = None
    currency: AscDesc | None = None
    mint: AscDesc | None = None
    issuing_state: AscDesc | None = None
