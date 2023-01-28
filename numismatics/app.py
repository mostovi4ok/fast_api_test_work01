from fastapi import FastAPI

from . import models, schemes
from .api import AccountResolver, CatalogResolve, MoneyResolve, TransferResolver, CrudResolve
from .db import engine

app = FastAPI()
CatalogResolve(schemes.Catalog, schemes.Catalog, models.TypeMoney).connect_with_app("/type_money", app)
CatalogResolve(schemes.Catalog, schemes.Catalog, models.Currency).connect_with_app("/currency", app)
CatalogResolve(schemes.Catalog, schemes.Catalog, models.Mint).connect_with_app("/mint", app)
CatalogResolve(schemes.Catalog, schemes.Catalog, models.IssuingState).connect_with_app("/issuing_state", app)
MoneyResolve().connect_with_app("/money", app)
AccountResolver().connect_with_app("/account", app)
TransferResolver().connect_with_app("/transfer", app)


@app.on_event("shutdown")
def shutdown_db() -> None:
    return engine.dispose()
