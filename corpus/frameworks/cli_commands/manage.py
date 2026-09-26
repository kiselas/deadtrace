import click


@click.group()
def cli() -> None:
    pass


@cli.command()
def export() -> None:
    pass


@cli.group()
def admin() -> None:
    pass


def orphan() -> None:
    pass


if __name__ == "__main__":
    cli()
