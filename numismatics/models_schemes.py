from datetime import datetime

from .schemes import BaseScheme
from .types import StatusTransfer


class BaseModelScheme(BaseScheme):
    id: int

    class Config:
        orm_mode = True


class CatalogModelScheme(BaseModelScheme):
    pass


class AccountModelScheme(BaseModelScheme):
    name: str
    is_admin: bool = False


class MoneyModelScheme(BaseModelScheme):
    description: str
    nominal_price: int
    release_year: str
    serial_number: str
    type_money: int
    currency: int
    mint: int
    issuing_state: int
    user: int


class TransferModelScheme(BaseModelScheme):
    source: int
    destination: int
    creater: int
    created_at: datetime
    closed_at: datetime | None = None
    comment: str
    money: int
    status: StatusTransfer
