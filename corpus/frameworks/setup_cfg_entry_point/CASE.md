# setup.cfg command is an entry point

`[options.entry_points]` declares `shop = _cli:run`. The command is a production root, so `run` is not a
candidate; `unused` in the same module is referenced nowhere.
