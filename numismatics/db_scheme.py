from .db import engine
from .models import Base


def create_all() -> None:
    Base.metadata.create_all(engine)


def drop_all() -> None:
    Base.metadata.drop_all(engine)
