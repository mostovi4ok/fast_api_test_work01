from pydantic import BaseModel


class BaseScheme(BaseModel):
    pass


class Catalog(BaseScheme):
    id: int

    class Config:
        orm_mode = True


class User(BaseScheme):
    id: int
    name: str

    class Config:
        orm_mode = True


class Money(BaseScheme):
    id: int
    description: str
    nominal_price: int
    release_year: str
    serial_namber: str
    type_money: int
    currency: int
    mint: int
    issuing_state: int
    user: int | None = None

    class Config:
        orm_mode = True


class CreateMoney(BaseScheme):
    description: str
    nominal_price: int
    release_year: str
    serial_namber: str
    type_money: int
    currency: int
    mint: int
    issuing_state: int
    user: int | None = None
