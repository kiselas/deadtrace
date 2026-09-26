# Typer and Click commands

`@app.command()` and `@app.callback()` on a module-level `typer.Typer()` register functions that
running the application calls. `@click.group()` makes a function a group, and `@cli.command()` or
`@cli.group()` registers a subcommand that invoking the group dispatches to. The commands run
when the application or group runs, although no project code calls them.

The unsafe outcome is reporting a command as unreached; the imprecise one is reaching commands
only conservatively, so that code they alone use can never be reported. A function that neither
framework registers is still reported.
