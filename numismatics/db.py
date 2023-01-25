from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from . import env

engine: Engine = create_engine(env.FAST_DB, echo=True)

SessionFactory = sessionmaker(engine, expire_on_commit=False)
