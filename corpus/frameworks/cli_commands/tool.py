import typer

app = typer.Typer()


@app.callback()
def main(verbose: bool = False) -> None:
    pass


@app.command()
def sync() -> None:
    pass


def forgotten() -> None:
    pass
