from typing import Literal

import click

from numismatics.db_scheme import create_all, drop_all


@click.command()
@click.option(
    "--db_action",
    default="create",
    type=click.Choice(["create", "drop"]),
)
def main(db_action: Literal["create", "drop"]) -> None:
    """Program for creating or deleting a database."""

    if db_action == "create":
        create_all()

    elif db_action == "drop":
        drop_all()


if __name__ == "__main__":
    main()
