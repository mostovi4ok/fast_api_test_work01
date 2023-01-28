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

from . import models, schemes, sql
from .depends import get_current_user, get_filters, get_ordering, get_session, get_super_user
from .errors import BaseError, MissingObjects, OwnerMismatch, UnauthorizedError, Undefined, UniqueError
from .middleware import session_middleware
from .types import StatusTransfer

CatalogRequestSchemeT = TypeVar("CatalogRequestSchemeT", bound=schemes.Catalog)
RequestSchemeT = TypeVar("RequestSchemeT", bound=schemes.BaseModel)
ResponseSchemeT = TypeVar("ResponseSchemeT", bound=schemes.BaseScheme)
ModelT = TypeVar("ModelT", bound=models.Base)


class CrudResolve(Generic[ResponseSchemeT, ModelT]):
    def __init__(self, response_scheme: type[ResponseSchemeT], model: type[ModelT]) -> None:
        self.response_scheme = response_scheme
        self.model = model

    def connect_with_app(self, prefix: str, app: FastAPI) -> None:
        app.include_router(self.get_router(), prefix=prefix, responses=self.get_response_details())
        app.middleware("http")(session_middleware)
        app.exception_handler(BaseError)(self.base_exception_handler)
        app.exception_handler(UnauthorizedError)(self.unauthorized_exception_handler)

    def get_response_details(self) -> dict[int | str, dict[str, Any]]:
        return {
            401: {
                "description": "Unauthorized",
                "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
            },
        }

    def get_router(self) -> APIRouter:
        api_router = APIRouter()
        self.connect_resolvers(api_router)
        return api_router

    def connect_resolvers(self, router: APIRouter) -> None:
        response_scheme = self.response_scheme
        responses: dict[str | int, dict[str, Any]] = {
            422: {
                "description": "Unprocessable Entity",
                "content": {"application/json": {"example": {"message": "Undefined"}}},
            }
        }
        router.get("/", response_model=Sequence[response_scheme])(self.get_all)
        router.get("/{obj_id}", response_model=response_scheme, responses=responses)(self.get_by_id)
        router.delete("/{obj_id}", responses=responses)(self.delete_by_id)

    def get_all(
        self, session: Session = Depends(get_session), user: models.Account = Depends(get_current_user)
    ) -> Sequence[ModelT]:
        return sql.get_all_instance(session, self.model, self.get_filtration(user))

    def get_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: models.Account = Depends(get_current_user)
    ) -> ModelT:
        return self.get_instance_by_id(session, obj_id, user)

    def delete_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: models.Account = Depends(get_super_user)
    ) -> None:
        obj = self.get_instance_by_id(session, obj_id, user)
        obj.deleted_at = datetime.now(timezone.utc)

    def get_instance_by_id(self, session: Session, obj_id: int, user: models.Account) -> ModelT:
        obj = sql.get_instance_by_id(session, obj_id, self.model, self.get_filtration(user))
        if obj is None:
            raise Undefined("undefined")

        return obj

    def get_filtration(self, user: models.Account) -> sql.OneModelFiltration[sql.OneModelStatement[ModelT]] | None:
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


class CatalogResolve(Generic[CatalogRequestSchemeT, ResponseSchemeT, ModelT], CrudResolve[ResponseSchemeT, ModelT]):
    def __init__(
        self, request_scheme: type[CatalogRequestSchemeT], response_scheme: type[ResponseSchemeT], model: type[ModelT]
    ) -> None:
        self.request_scheme = request_scheme
        super().__init__(response_scheme, model)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.post("/", response_model=self.response_scheme)(self.create)
        super().connect_resolvers(router)

    def create(
        self, session: Session = Depends(get_session), admin: models.Account = Depends(get_super_user)
    ) -> ModelT:
        obj = self.model()
        session.add(obj)
        session.flush()
        return obj


class CrudUpdateResolver(Generic[RequestSchemeT, ResponseSchemeT, ModelT], CrudResolve[ResponseSchemeT, ModelT]):
    def __init__(
        self, request_scheme: type[RequestSchemeT], response_scheme: type[ResponseSchemeT], model: type[ModelT]
    ) -> None:
        self.request_scheme = request_scheme
        super().__init__(response_scheme, model)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.post("/", response_model=self.response_scheme)(self.create)
        router.post(
            "/{obj_id}",
            response_model=self.response_scheme,
            responses={
                422: {
                    "description": "Unprocessable Entity",
                    "content": {"application/json": {"example": {"message": "Undefined"}}},
                }
            },
        )(self.update)
        super().connect_resolvers(router)

    def create(
        self,
        scheme: RequestSchemeT,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_current_user),
    ) -> ModelT:
        raise NotImplementedError()

    def create_model(
        self,
        scheme: RequestSchemeT,
        session: Session,
        user: models.Account,
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
        user: models.Account = Depends(get_current_user),
    ) -> ModelT:
        raise NotImplementedError()

    def update_model(
        self,
        obj_id: int,
        scheme: RequestSchemeT,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_current_user),
    ) -> ModelT:
        self.validate(session, scheme)
        obj = self.get_instance_by_id(session, obj_id, user)
        for field, value in scheme.dict().items():
            setattr(obj, field, value)

        return obj

    def get_new_instance_fields(self, user: models.Account) -> dict[str, Any]:
        return {}

    def validate(self, session: Session, scheme: RequestSchemeT) -> None:
        pass


class MoneyResolve(CrudUpdateResolver[schemes.CreateMoney, schemes.Money, models.Money]):
    fields: dict[str, type[models.Catalog]] = {
        "type_money": models.TypeMoney,
        "currency": models.Currency,
        "mint": models.Mint,
        "issuing_state": models.IssuingState,
    }

    def __init__(self) -> None:
        super().__init__(schemes.CreateMoney, schemes.Money, models.Money)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.get("/all", response_model=Sequence[schemes.Money])(self.get_all_money_for_super_user)
        router.get("/upload", response_model=Sequence[schemes.Money])(self.upload_collection)
        super().connect_resolvers(router)

    def create(
        self,
        scheme: schemes.CreateMoney,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_current_user),
    ) -> models.Money:
        return super().create_model(scheme, session, user)

    def update(
        self,
        obj_id: int,
        scheme: schemes.CreateMoney,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_current_user),
    ) -> models.Money:
        return super().update_model(obj_id, scheme, session, user)

    def get_all_money_for_super_user(
        self, session: Session = Depends(get_session), user: models.Account = Depends(get_super_user)
    ) -> Sequence[models.Money]:
        return sql.get_all_instance(session, self.model)

    def get_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: models.Account = Depends(get_current_user)
    ) -> models.Money:
        if user.is_admin:
            return super().get_by_id(obj_id, session, user)

        return self.get_instance_by_id(session, obj_id, user)

    def delete_by_id(
        self, obj_id: int, session: Session = Depends(get_session), user: models.Account = Depends(get_current_user)
    ) -> None:
        super().delete_by_id(obj_id, session, user)

    def upload_collection(
        self,
        order_by: dict[str, Any] = Depends(get_ordering),
        filters: dict[str, Any] = Depends(get_filters(schemes.Filtration)),
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_current_user),
    ) -> StreamingResponse:
        converters = {"+": asc, "-": desc}
        stmt = sql.select_and_filter(self.model, self.get_filtration(user)).filter_by(**filters)
        if order_by:
            stmt = stmt.order_by(None).order_by(*[converters[sort](field) for field, sort in order_by.items()])

        money = session.scalars(stmt).all()
        return self.dump_csv(money, list(schemes.Money.__fields__.keys()))

    def dump_csv(self, data: Sequence[models.Money], headers: Sequence[str]) -> StreamingResponse:
        buffer_file = StringIO()
        writer = csv.writer(buffer_file, dialect=csv.excel)
        writer.writerow(headers)
        writer.writerows([getattr(money, r) for r in headers] for money in data)
        buffer_file.seek(0)
        return StreamingResponse(
            buffer_file, media_type="text/csv", headers={"Content-Disposition": "filename=money.csv"}
        )

    def get_new_instance_fields(self, user: models.Account) -> dict[str, Any]:
        return {"user": user.id}

    def get_filtration(
        self, user: models.Account
    ) -> sql.OneModelFiltration[sql.OneModelStatement[models.Money]] | None:
        def accesse_filter(stmt: sql.OneModelStatement[models.Money]) -> sql.OneModelStatement[models.Money]:
            return stmt.where(models.Money.user == user.id)

        return accesse_filter

    def validate(self, session: Session, scheme: schemes.CreateMoney) -> None:
        fk_select = [
            select(literal_column(f"'{attr}'")).where(
                model.id == getattr(scheme, attr), sql.get_filter_by_existing(model)
            )
            for attr, model in self.fields.items()
        ]
        stmt_by_tabls = fk_select[0].union_all(*fk_select[1:])
        existing = session.scalars(stmt_by_tabls).all()

        if missing_keys := Counter(self.fields.keys()) - Counter(existing):
            raise MissingObjects(list(missing_keys))


class AccountResolver(CrudUpdateResolver[schemes.NewAccount, schemes.Account, models.Account]):
    def __init__(self) -> None:
        super().__init__(schemes.NewAccount, schemes.Account, models.Account)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.get("/me", response_model=schemes.Account)(get_current_user)
        super().connect_resolvers(router)

    def create(
        self,
        scheme: schemes.NewAccount,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_super_user),
    ) -> models.Account:
        return super().create_model(scheme, session, user)

    def update(
        self,
        obj_id: int,
        scheme: schemes.NewAccount,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_super_user),
    ) -> models.Account:
        return super().update_model(obj_id, scheme, session, user)

    def validate(self, session: Session, scheme: schemes.NewAccount) -> None:
        stmt = select(self.model).where(self.model.name == scheme.name, sql.get_filter_by_existing(self.model))
        account = session.scalar(stmt)
        if account:
            raise UniqueError


class TransferResolver(CrudResolve[schemes.Transfer, models.Transfer]):
    request_scheme = schemes.CreateTransfer

    def __init__(self) -> None:
        super().__init__(schemes.Transfer, models.Transfer)

    def connect_resolvers(self, router: APIRouter) -> None:
        router.post("/", response_model=schemes.Transfer)(self.create_transfer)
        router.post("/approve/{{obj_id}}", response_model=schemes.Money)(self.approve)
        router.post("/decline/{{obj_id}}")(self.decline)
        super().connect_resolvers(router)

    def create_transfer(
        self,
        scheme: schemes.CreateTransfer,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_super_user),
    ) -> models.Transfer:
        source = sql.get_instance_by_id(session, scheme.source, models.Account)
        destination = sql.get_instance_by_id(session, scheme.destination, models.Account)
        money = sql.get_instance_by_id(session, scheme.money, models.Money)
        if source is None or destination is None or money is None:
            raise MissingObjects()

        if money.user != source.id:
            raise OwnerMismatch()

        transfer = models.Transfer(
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
        user: models.Account = Depends(get_current_user),
    ) -> models.Money:
        transfer = self.get_instance_by_id(session, obj_id, user)
        money = sql.get_instance_by_id(session, transfer.money, models.Money)
        if money and money.user == transfer.source:
            return self.move_money(transfer, money, user)

        raise MissingObjects(transfer.money)

    def move_money(self, transfer: models.Transfer, money: models.Money, user: models.Account) -> models.Money:
        transfer.closed_at = datetime.now(timezone.utc)
        transfer.status = StatusTransfer.approved
        money.user = user.id
        return money

    def decline(
        self,
        obj_id: int,
        session: Session = Depends(get_session),
        user: models.Account = Depends(get_current_user),
    ) -> None:
        transfer = self.get_instance_by_id(session, obj_id, user)
        transfer.closed_at = datetime.now(timezone.utc)
        transfer.status = StatusTransfer.declined

    def get_filtration(
        self, user: models.Account
    ) -> sql.OneModelFiltration[sql.OneModelStatement[models.Transfer]] | None:
        def accesse_filter(stmt: sql.OneModelStatement[models.Transfer]) -> sql.OneModelStatement[models.Transfer]:
            stmt = stmt.where(self.model.status == StatusTransfer.initial)
            if user.is_admin:
                return stmt

            return stmt.where(self.model.destination == user.id)

        return accesse_filter
