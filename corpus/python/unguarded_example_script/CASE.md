# An example script without a main guard

`examples/plugin_example.py` ends with a top-level call and nothing imports it: it exists to be run.
Its top-level code calls `setup`, which calls `parse_items` and `total`; they are used.
`never_called` is referenced nowhere and stays a candidate.
