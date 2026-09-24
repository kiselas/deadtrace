# Scripts and `__main__` modules

The project declares no worlds, entry points, or applications. `report.py` and
`_maintenance/cleanup.py` run code under `if __name__ == "__main__":`, and
`_maintenance/__main__.py` runs when the package is executed with `python -m`. Each is a
root of the automatic `production:scripts` world, so `strip_rows` and `print_usage`, used
only there, are live. The public module `report` is also library API. A main guard in a
test module does not make its callee production code, and `unused_control` stays a
candidate.
