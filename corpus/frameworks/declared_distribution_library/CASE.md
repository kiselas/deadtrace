# A declared distribution shipped next to example scripts

`pyproject.toml` declares the distribution `demo-kit`, and the package `demo_kit` exists in the
source. The repository also holds `examples/run.py`, a script with a main guard, and declares no command of its own. Users of the
distribution call its public API, so `Client` and `Client.fetch` run whatever the examples do; the
script world alone would make them look unreached. `_unused` is private and referenced nowhere,
so the case cannot be met by weakening the world.
