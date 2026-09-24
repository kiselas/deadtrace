import click


@click.command()
def cli() -> None:
    print("cli")


def main() -> None:
    print("main")
