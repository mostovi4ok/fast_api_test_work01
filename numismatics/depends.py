from typing import Any, Callable, TypeVar

from fastapi import Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import UnauthorizedError
from .models import Account
from .schemes import BaseScheme, Ordering

SchemeT = TypeVar("SchemeT", bound=BaseScheme)

security: HTTPBasic = HTTPBasic()


def get_session(request: Request) -> Session:
    session = getattr(request.state, "session", None)
    assert session is not None
    return session


def get_current_user(
    session: Session = Depends(get_session), credentials: HTTPBasicCredentials = Depends(security)
) -> Account:
    current_username = credentials.username
    query = select(Account).where(Account.name == current_username)
    if (obj := session.scalar(query)) is None:
        raise UnauthorizedError("undefined user")

    return obj


def get_super_user(user: Account = Depends(get_current_user)) -> Account:
    if user.is_admin:
        return user

    raise UnauthorizedError("no admin")


def get_filters(base_scheme: type[SchemeT]) -> Callable[[SchemeT], dict[str, Any]]:
    def unwrap_scheme(scheme: SchemeT = Depends(base_scheme)) -> dict[str, Any]:
        return scheme.dict(exclude_none=True)

    return unwrap_scheme


def get_ordering(order_by: str | None = None) -> dict[str, Any]:
    if not order_by:
        return {}

    fields = {
        part.lstrip("+").lstrip("-"): (part[0] if part[:1] in "+-" else "+")
        for part in order_by.strip().split(",")
        if part
    }
    return Ordering.parse_obj(fields).dict(exclude_none=True)
