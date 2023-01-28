import click

from numismatics.db import SessionFactory
from numismatics.models import Account


@click.command()
@click.option("--name")
def main(name: str) -> None:
    with SessionFactory() as session:
        with session.begin():
            user = Account(name=name, is_admin=True)
            session.add(user)


if __name__ == "__main__":
    main()
