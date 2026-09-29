import typer

app = typer.Typer()


@app.command()
def hello() -> None:
    print("hello")
