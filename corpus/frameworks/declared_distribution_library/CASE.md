# A declared distribution shipped next to example scripts

`pyproject.toml` declares the distribution `demo-kit`, and the package `demo_kit` exists in the
source. The project also declares a console script, `demo_kit.cli:main`, which is an entry-point world. Users of the
distribution call its public API, so `Client` and `Client.fetch` run whatever the command does; the
entry-point world alone would make them look unreached. `_unused` is private and referenced nowhere,
so the case cannot be met by weakening the world.
