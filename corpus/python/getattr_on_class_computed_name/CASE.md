# getattr on a class with a computed name

`Datasets.load` reads `getattr(Datasets, f"_process_{name}")` from the class itself and calls the
value. Any static method whose name starts with `_process_` may run, so `_process_gsm8k` and
`_process_coin` are protected by an unknown boundary. `_unrelated` does not fit the name and is
called by nothing.
