from fastapi import Request, Response

from .db import SessionFactory


async def session_middleware(request: Request, call_next) -> Response:
    with SessionFactory() as session:
        with session.begin():
            request.state.session = session
            return await call_next(request)
