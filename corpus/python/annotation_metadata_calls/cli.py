from __future__ import annotations

from typing import Annotated

import typer
from pydantic import AfterValidator, BaseModel

app = typer.Typer()


def show_version(value: bool) -> None:
    if value:
        raise typer.Exit()


def normalize(value: str) -> str:
    return value.strip()


class Target(BaseModel):
    name: Annotated[str, AfterValidator(normalize)]


def unused_helper() -> None:
    pass


@app.command()
def main(
    name: str,
    version: Annotated[bool, typer.Option(callback=show_version)] = False,
) -> None:
    print(Target(name=name))


if __name__ == "__main__":
    app()
