from fastapi import FastAPI

from . import models, schemes
from .api import CatalogResolve, MoneyResolve
from .db import engine

app = FastAPI()

app.mount("/type_money/", CatalogResolve(schemes.Catalog, schemes.Catalog, models.TypeMoney).resolve_api())
app.mount("/currency/", CatalogResolve(schemes.Catalog, schemes.Catalog, models.Currency).resolve_api())
app.mount("/mint/", CatalogResolve(schemes.Catalog, schemes.Catalog, models.Mint).resolve_api())
app.mount("/issuing_state/", CatalogResolve(schemes.Catalog, schemes.Catalog, models.IssuingState).resolve_api())
app.mount("/money/", MoneyResolve().resolve_api())


@app.on_event("shutdown")
def shutdown_db() -> None:
    return engine.dispose()
