import csv
import http
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import asc, desc, literal_column

from . import sql
from .depends import get_current_user, get_filters, get_ordering, get_session, get_super_user
from .errors import (
    BaseError,
    MissingObjectsError,
    OwnerMismatchError,
    SelfTransferError,
    UnauthorizedError,
    UndefinedError,
    UniqueError,
)
from .middleware import session_middleware
from .models import Account, BaseModel, Catalog, Currency, IssuingState, Mint, Money, Transfer, TypeMoney
from .models_schemes import AccountModelScheme, BaseModelScheme, MoneyModelScheme, TransferModelScheme
from .schemes import (
    BaseScheme,
    CatalogScheme,
    CreateMoneyScheme,
    CreateTransferScheme,
    FiltrationScheme,
    NewAccountScheme,
)
from .types import StatusTransfer

CatalogRequestSchemeT = TypeVar("CatalogRequestSchemeT", bound=CatalogScheme)
RequestSchemeT = TypeVar("RequestSchemeT", bound=BaseScheme)
ResponseSchemeT = TypeVar("ResponseSchemeT", bound=BaseModelScheme)
ModelT = TypeVar("ModelT", bound=BaseModel)

errors_responses: dict[int | str, dict[int | str, dict[str, Any]]] = {
    401: {
        401: {
            "description": "Unauthorized",
            "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
        }
    },
    422: {
        422: {
            "description": "Unprocessable Entity",
            "content": {"application/json": {"example": {"message": "Undefined"}}},
        }
    },
}


class CrudResolver(Generic[ResponseSchemeT, ModelT]):
    def __init__(self, response_scheme: type[ResponseSchemeT], model: type[ModelT]) -> None:
        self.response_scheme = response_scheme
        self.model = model

    def connect_with_app(self, prefix: str, app: FastAPI) -> None:
        app.include_router(self.get_router(), prefix=prefix, responses=errors_responses[401])
        app.middleware("http")(session_middleware)
        app.exception_handler(BaseError)(self.base_exception_handler)
        app.exception_handler(UnauthorizedError)(self.unauthorized_exception_handler)

    def get_router(self) -> APIRouter:
        api_router = APIRouter()
        self.connect_resolvers(api_router)
        return api_router

    def connect_resolvers(self, router: APIRouter) -> None:
        response_scheme = self.response_scheme
        router.get("/", response_model=Sequence[response_scheme])(self.get_all)
        router.get("/{obj_id}", response_model=response_scheme, responses=errors_responses[422])(self.get_by_id)
        router.delete("/{obj_id}", responses=errors_responses[422])(self.delete_by_id)

    def get_all(
        self, session: Session = Depends(get_session), user: Account = Depends(get_current_user)
    ) -> Sequence[ModelT]:
        return sql.get_all_instance(session, self.model, self.get_filtration(user))

    def get_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: Account = Depends(get_current_user)
    ) -> ModelT:
        return self.get_instance_by_id(session, obj_id, user)

    def delete_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: Account = Depends(get_super_user)
    ) -> None:
        obj = self.get_instance_by_id(session, obj_id, user)
        obj.deleted_at = datetime.now(timezone.utc)

    def get_instance_by_id(self, session: Session, obj_id: int, user: Account) -> ModelT:
        obj = sql.get_instance_by_id(session, obj_id, self.model, self.get_filtration(user))
        if obj is None:
            raise UndefinedError("undefined")

        return obj

    def get_filtration(self, user: Account) -> sql.OneModelFiltration[sql.OneModelStatement[ModelT]] | None:
        return None

    def base_exception_handler(self, request: Request, exc: BaseError) -> JSONResponse:
        return JSONResponse(
            status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY,
            content={"message": exc.__class__.__name__},
        )

    def unauthorized_exception_handler(self, request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(
            status_code=http.HTTPStatus.FORBIDDEN,
            content={"message": exc.__class__.__name__},
        )


class CatalogResolver(Generic[CatalogRequestSchemeT, ResponseSchemeT, ModelT], CrudResolver[ResponseSchemeT, ModelT]):
    def __init__(
        self, request_scheme: type[CatalogRequestSchemeT], response_scheme: type[ResponseSchemeT], model: type[ModelT]
    ) -> None:
        self.request_scheme = request_scheme
        super().__init__(response_scheme, model)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.post("/", response_model=self.response_scheme)(self.create)
        super().connect_resolvers(router)

    def create(self, session: Session = Depends(get_session), admin: Account = Depends(get_super_user)) -> ModelT:
        obj = self.model()
        session.add(obj)
        session.flush()
        return obj


class CrudUpdateResolver(Generic[RequestSchemeT, ResponseSchemeT, ModelT], CrudResolver[ResponseSchemeT, ModelT]):
    def __init__(
        self, request_scheme: type[RequestSchemeT], response_scheme: type[ResponseSchemeT], model: type[ModelT]
    ) -> None:
        self.request_scheme = request_scheme
        super().__init__(response_scheme, model)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.post("/", response_model=self.response_scheme)(self.create)
        router.post("/{obj_id}", response_model=self.response_scheme, responses=errors_responses[422])(self.update)
        super().connect_resolvers(router)

    def create(
        self,
        scheme: RequestSchemeT,
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> ModelT:
        raise NotImplementedError()

    def create_model(
        self,
        scheme: RequestSchemeT,
        session: Session,
        user: Account,
    ) -> ModelT:
        self.validate(session, scheme)
        obj = self.model(**scheme.dict(), **self.get_new_instance_fields(user))
        session.add(obj)
        session.flush()
        return obj

    def update(
        self,
        obj_id: int,
        scheme: RequestSchemeT,
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> ModelT:
        raise NotImplementedError()

    def update_model(
        self,
        obj_id: int,
        scheme: RequestSchemeT,
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> ModelT:
        self.validate(session, scheme)
        obj = self.get_instance_by_id(session, obj_id, user)
        for field, value in scheme.dict().items():
            setattr(obj, field, value)

        return obj

    def get_new_instance_fields(self, user: Account) -> dict[str, Any]:
        return {}

    def validate(self, session: Session, scheme: RequestSchemeT) -> None:
        pass


class MoneyResolver(CrudUpdateResolver[CreateMoneyScheme, MoneyModelScheme, Money]):
    fields: dict[str, type[Catalog]] = {
        "type_money": TypeMoney,
        "currency": Currency,
        "mint": Mint,
        "issuing_state": IssuingState,
    }

    def __init__(self) -> None:
        super().__init__(CreateMoneyScheme, MoneyModelScheme, Money)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.get("/all", response_model=Sequence[MoneyModelScheme])(self.get_all_money_for_super_user)
        router.get("/upload", response_model=Sequence[MoneyModelScheme])(self.upload_collection)
        super().connect_resolvers(router)

    def create(
        self,
        scheme: CreateMoneyScheme,
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> Money:
        return super().create_model(scheme, session, user)

    def update(
        self,
        obj_id: int,
        scheme: CreateMoneyScheme,
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> Money:
        return super().update_model(obj_id, scheme, session, user)

    def get_all_money_for_super_user(
        self, session: Session = Depends(get_session), user: Account = Depends(get_super_user)
    ) -> Sequence[Money]:
        return sql.get_all_instance(session, self.model)

    def get_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: Account = Depends(get_current_user)
    ) -> Money:
        if user.is_admin:
            return super().get_by_id(obj_id, session, user)

        return self.get_instance_by_id(session, obj_id, user)

    def delete_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: Account = Depends(get_current_user)
    ) -> None:
        super().delete_by_id(obj_id, session, user)

    def upload_collection(
        self,
        order_by: dict[str, Any] = Depends(get_ordering),
        filters: dict[str, Any] = Depends(get_filters(FiltrationScheme)),
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> StreamingResponse:
        converters = {"+": asc, "-": desc}
        stmt = sql.select_and_filter(self.model, self.get_filtration(user)).filter_by(**filters)
        if order_by:
            stmt = stmt.order_by(None).order_by(*[converters[sort](field) for field, sort in order_by.items()])

        money = session.scalars(stmt).all()
        return self.dump_csv(money, list(MoneyModelScheme.__fields__.keys()))

    def dump_csv(self, data: Sequence[Money], headers: Sequence[str]) -> StreamingResponse:
        buffer_file = StringIO()
        writer = csv.writer(buffer_file, dialect=csv.excel)
        writer.writerow(headers)
        writer.writerows([getattr(money, r) for r in headers] for money in data)
        buffer_file.seek(0)
        return StreamingResponse(
            buffer_file, media_type="text/csv", headers={"Content-Disposition": "filename=money.csv"}
        )

    def get_new_instance_fields(self, user: Account) -> dict[str, Any]:
        return {"user": user.id}

    def get_filtration(self, user: Account) -> sql.OneModelFiltration[sql.OneModelStatement[Money]] | None:
        def accesse_filter(stmt: sql.OneModelStatement[Money]) -> sql.OneModelStatement[Money]:
            return stmt.where(Money.user == user.id)

        return accesse_filter

    def validate(self, session: Session, scheme: CreateMoneyScheme) -> None:
        fk_select = [
            select(literal_column(f"'{attr}'")).where(
                model.id == getattr(scheme, attr), sql.get_filter_by_existing(model)
            )
            for attr, model in self.fields.items()
        ]
        stmt_by_tabls = fk_select[0].union_all(*fk_select[1:])
        existing = session.scalars(stmt_by_tabls).all()

        if missing_keys := Counter(self.fields.keys()) - Counter(existing):
            raise MissingObjectsError(list(missing_keys))


class AccountResolver(CrudUpdateResolver[NewAccountScheme, AccountModelScheme, Account]):
    def __init__(self) -> None:
        super().__init__(NewAccountScheme, AccountModelScheme, Account)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.get("/me", response_model=AccountModelScheme)(get_current_user)
        super().connect_resolvers(router)

    def create(
        self,
        scheme: NewAccountScheme,
        session: Session = Depends(get_session),
        user: Account = Depends(get_super_user),
    ) -> Account:
        return super().create_model(scheme, session, user)

    def update(
        self,
        obj_id: int,
        scheme: NewAccountScheme,
        session: Session = Depends(get_session),
        user: Account = Depends(get_super_user),
    ) -> Account:
        return super().update_model(obj_id, scheme, session, user)

    def validate(self, session: Session, scheme: NewAccountScheme) -> None:
        stmt = select(self.model).where(self.model.name == scheme.name, sql.get_filter_by_existing(self.model))
        account = session.scalar(stmt)
        if account:
            raise UniqueError


class TransferResolver(CrudResolver[TransferModelScheme, Transfer]):
    request_scheme = CreateTransferScheme

    def __init__(self) -> None:
        super().__init__(TransferModelScheme, Transfer)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.post("/", response_model=TransferModelScheme)(self.create_transfer)
        router.post("/approve/{{obj_id}}", response_model=MoneyModelScheme)(self.approve)
        router.post("/decline/{{obj_id}}")(self.decline)
        super().connect_resolvers(router)

    def create_transfer(
        self,
        scheme: CreateTransferScheme,
        session: Session = Depends(get_session),
        user: Account = Depends(get_super_user),
    ) -> Transfer:
        source, destination, money = self.validate_transfer(scheme, session)
        transfer = Transfer(
            source=source.id,
            destination=destination.id,
            creater=user.id,
            created_at=datetime.now(timezone.utc),
            comment=scheme.comment,
            money=money.id,
            status=StatusTransfer.initial,
        )
        session.add(transfer)
        session.flush()
        return transfer

    def approve(
        self,
        obj_id: int,
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> Money:
        transfer = self.get_instance_by_id(session, obj_id, user)
        money = sql.get_instance_by_id(session, transfer.money, Money, lambda stmt: stmt.with_for_update())
        if money and money.user == transfer.source:
            return self.move_money(transfer, money, user)

        raise MissingObjectsError(transfer.money)

    def move_money(self, transfer: Transfer, money: Money, user: Account) -> Money:
        transfer.closed_at = datetime.now(timezone.utc)
        transfer.status = StatusTransfer.approved
        money.user = user.id
        return money

    def decline(
        self,
        obj_id: int,
        session: Session = Depends(get_session),
        user: Account = Depends(get_current_user),
    ) -> None:
        transfer = self.get_instance_by_id(session, obj_id, user)
        transfer.closed_at = datetime.now(timezone.utc)
        transfer.status = StatusTransfer.declined

    def get_filtration(self, user: Account) -> sql.OneModelFiltration[sql.OneModelStatement[Transfer]] | None:
        def accesse_filter(stmt: sql.OneModelStatement[Transfer]) -> sql.OneModelStatement[Transfer]:
            stmt = stmt.where(self.model.status == StatusTransfer.initial)
            if user.is_admin:
                return stmt

            return stmt.where(self.model.destination == user.id)

        return accesse_filter

    def get_filtration_by_source(
        self, user: Account, money: Money
    ) -> sql.OneModelFiltration[sql.OneModelStatement[Transfer]] | None:
        def accesse_filter(stmt: sql.OneModelStatement[Transfer]) -> sql.OneModelStatement[Transfer]:
            return stmt.where(
                self.model.source == user.id,
                self.model.money == money.id,
                self.model.status == StatusTransfer.initial,
            )

        return accesse_filter

    def validate_transfer(self, scheme: CreateTransferScheme, session: Session) -> tuple[Account, Account, Money]:
        source = sql.get_instance_by_id(session, scheme.source, Account)
        destination = sql.get_instance_by_id(session, scheme.destination, Account)
        money = sql.get_instance_by_id(session, scheme.money, Money, lambda stmt: stmt.with_for_update())

        if source is None or destination is None or money is None:
            raise MissingObjectsError()

        if money.user != source.id:
            raise OwnerMismatchError()

        if source.id == destination.id:
            raise SelfTransferError()

        duplicate_transfers = sql.get_all_instance(session, Transfer, self.get_filtration_by_source(source, money))
        if duplicate_transfers:
            raise UniqueError()

        return source, destination, money
