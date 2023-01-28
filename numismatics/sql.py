from collections.abc import Sequence
from typing import Callable, TypeAlias, TypeVar

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.orm import Session

from .models import Base

ModelT = TypeVar("ModelT", bound=Base)
OneModelStatement: TypeAlias = Select[tuple[ModelT]]
SelectT = TypeVar("SelectT", bound=Select)
OneModelFiltration: TypeAlias = Callable[[SelectT], SelectT]


def get_instance_by_id(
    session: Session,
    obj_id: int,
    model: type[ModelT],
    filtration: OneModelFiltration[OneModelStatement[ModelT]] | None = None,
) -> ModelT | None:
    return session.scalar(select_and_filter(model, filtration).where(model.id == obj_id))


def get_all_instance(
    session: Session,
    model: type[ModelT],
    filtration: OneModelFiltration[OneModelStatement[ModelT]] | None = None,
) -> Sequence[ModelT]:
    return session.scalars(select_and_filter(model, filtration).order_by(model.id)).all()


def select_and_filter(
    model: type[ModelT], filtration: OneModelFiltration[OneModelStatement[ModelT]] | None = None
) -> OneModelStatement[ModelT]:
    stmt = select(model).where(get_filter_by_existing(model))
    if filtration is not None:
        stmt = filtration(stmt)

    return stmt


def get_filter_by_existing(model: type[Base]) -> ColumnElement[bool]:
    return model.deleted_at == None
