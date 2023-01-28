from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, validator, PositiveInt

from .types import StatusTransfer


def validate_length_str(field: str, length: int) -> Any:
    @validator(field, allow_reuse=True)
    def str_length(cls, value) -> str:
        if value is None or 0 < len(value) < length:
            return value

        raise ValueError("invalid length")

    return str_length


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

    name_length = validate_length_str("name", 30)


class Account(ModelScheme):
    name: str
    is_admin: bool = False


class Money(ModelScheme):
    description: str
    nominal_price: int
    release_year: str
    serial_number: str
    type_money: int
    currency: int
    mint: int
    issuing_state: int
    user: int


class CreateMoney(BaseScheme):
    description: str
    nominal_price: int
    release_year: str
    serial_number: str
    type_money: PositiveInt
    currency: PositiveInt
    mint: PositiveInt
    issuing_state: PositiveInt

    description_length = validate_length_str("description", 100)
    release_year_length = validate_length_str("release_year", 4)
    serial_number_length = validate_length_str("serial_number", 30)


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
    source: PositiveInt
    destination: PositiveInt
    comment: str
    money: PositiveInt

    comment_length = validate_length_str("comment", 100)


class Filtration(BaseScheme):
    id: PositiveInt | None = None
    description: str | None = None
    nominal_price: PositiveInt | None = None
    release_year: str | None = None
    serial_number: str | None = None
    type_money: PositiveInt | None = None
    currency: PositiveInt | None = None
    mint: PositiveInt | None = None
    issuing_state: PositiveInt | None = None

    description_length = validate_length_str("description", 100)
    release_year_length = validate_length_str("release_year", 4)
    serial_number_length = validate_length_str("serial_number", 30)


AscDesc = Literal["+", "-"]


class Ordering(BaseScheme):
    id: AscDesc | None = None
    description: AscDesc | None = None
    nominal_price: AscDesc | None = None
    release_year: AscDesc | None = None
    serial_number: AscDesc | None = None
    type_money: AscDesc | None = None
    currency: AscDesc | None = None
    mint: AscDesc | None = None
    issuing_state: AscDesc | None = None
