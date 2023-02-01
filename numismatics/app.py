from fastapi import FastAPI

from .api import AccountResolver, CatalogResolver, MoneyResolver, TransferResolver
from .db import engine
from .models import Currency, IssuingState, Mint, TypeMoney
from .models_schemes import CatalogModelScheme
from .schemes import CatalogScheme

app = FastAPI()

CatalogResolver(CatalogScheme, CatalogModelScheme, TypeMoney).connect_with_app("/type_money", app)
CatalogResolver(CatalogScheme, CatalogModelScheme, Currency).connect_with_app("/currency", app)
CatalogResolver(CatalogScheme, CatalogModelScheme, Mint).connect_with_app("/mint", app)
CatalogResolver(CatalogScheme, CatalogModelScheme, IssuingState).connect_with_app("/issuing_state", app)
MoneyResolver().connect_with_app("/money", app)
AccountResolver().connect_with_app("/account", app)
TransferResolver().connect_with_app("/transfer", app)


@app.on_event("shutdown")
def shutdown_db() -> None:
    return engine.dispose()
