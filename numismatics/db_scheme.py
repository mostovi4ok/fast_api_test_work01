from .db import engine
from .models import BaseModel


def create_all() -> None:
    BaseModel.metadata.create_all(engine)


def drop_all() -> None:
    BaseModel.metadata.drop_all(engine)
