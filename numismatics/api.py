from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Generic, TypeVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import literal_column

from . import models, schemes
from .db import SessionFactory
from .errors import BaseError, MissingObjects, Undefined

RequestSchemeT = TypeVar("RequestSchemeT", bound=schemes.Catalog)
ResponseSchemeT = TypeVar("ResponseSchemeT")

ModelT = TypeVar("ModelT", bound=models.Base)


class CrudResolve(Generic[ResponseSchemeT, ModelT]):
    def __init__(self, response_scheme: type[ResponseSchemeT], model: type[ModelT]) -> None:
        self.response_scheme = response_scheme
        self.model = model

    def resolve_api(self) -> FastAPI:
        api = FastAPI()
        response_scheme = self.response_scheme
        api.get("/", response_model=Sequence[response_scheme])(self.get_all)
        api.get("/{obj_id}", response_model=response_scheme)(self.get_by_id)
        api.delete("/{obj_id}")(self.delete_by_id)
        api.exception_handler(BaseError)(self.unicorn_exception_handler)
        return api

    def get_all(self) -> Sequence[ModelT]:
        with self.session as session:
            stmt = select(self.model).order_by(self.model.id)
            return session.scalars(stmt).all()

    def get_by_id(self, obj_id: int) -> ModelT:
        with self.session as session:
            return self.get_instance_by_id(session, obj_id)

    def delete_by_id(self, obj_id: int) -> None:
        with self.session as session:
            obj = self.get_instance_by_id(session, obj_id)
            session.delete(obj)

    def get_instance_by_id(self, session: Session, obj_id: int) -> ModelT:
        query = select(self.model).where(self.model.id == obj_id)
        if (obj := session.scalar(query)) is None:
            raise Undefined("undefined")
        return obj

    @property
    @contextmanager
    def session(self) -> Iterator[Session]:
        with SessionFactory() as session:
            with session.begin():
                yield session

    def unicorn_exception_handler(self, request: Request, exc: BaseError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"message": exc.__class__.__name__},
        )


class CatalogResolve(Generic[RequestSchemeT, ResponseSchemeT, ModelT], CrudResolve[ResponseSchemeT, ModelT]):
    def __init__(
        self, request_scheme: type[RequestSchemeT], response_scheme: type[ResponseSchemeT], model: type[ModelT]
    ) -> None:
        self.request_scheme = request_scheme
        super().__init__(response_scheme, model)

    def resolve_api(self) -> FastAPI:
        api = super().resolve_api()
        api.post("/", response_model=self.response_scheme)(self.create)
        return api

    def create(self) -> ModelT:
        with self.session as session:
            obj = self.model()
            session.add(obj)
            return obj


class MoneyResolve(CrudResolve[schemes.Money, models.Money]):
    fields: dict[str, type[models.Catalog]] = {
        "type_money": models.TypeMoney,
        "currency": models.Currency,
        "mint": models.Mint,
        "issuing_state": models.IssuingState,
    }
    request_scheme: type[schemes.CreateMoney] = schemes.CreateMoney

    def __init__(self) -> None:
        super().__init__(schemes.Money, models.Money)

    def create(self, scheme: schemes.CreateMoney) -> models.Money:
        with self.session as session:
            self.validate(session, scheme)
            obj = self.model(**scheme.dict())

            session.add(obj)
            return obj

    def update(self, obj_id: int, scheme: schemes.CreateMoney) -> models.Money:
        with self.session as session:
            self.validate(session, scheme)
            obj = self.get_instance_by_id(session, obj_id)
            for name, value in scheme.dict().items():
                setattr(obj, name, value)
        return obj

    def validate(self, session: Session, scheme: schemes.CreateMoney) -> None:
        fk_select = [
            select(literal_column(f"'{attr}'")).where(model.id == getattr(scheme, attr))
            for attr, model in self.fields.items()
        ]
        stmt_by_tabls = fk_select[0].union_all(*fk_select[1:])
        existing = session.scalars(stmt_by_tabls).all()

        if missing_keys := Counter(self.fields.keys()) - Counter(existing):
            raise MissingObjects(list(missing_keys))

    def resolve_api(self) -> FastAPI:
        api = super().resolve_api()

        api.post("/", response_model=self.response_scheme)(self.create)
        api.post("/{obj_id}", response_model=self.response_scheme)(self.update)
        return api
