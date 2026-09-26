# pytest hooks, plugin fixtures, and collection settings

pytest calls the `pytest_*` hooks of `conftest.py` files, and pytest-asyncio requests the
`event_loop` fixture a project overrides. The configuration's `python_files` decides which
modules are test modules: here `check_*.py`, so `checks/check_orders.py` is collected and
`checks/test_legacy.py` is not.

The unsafe outcome is reporting the hooks, the overriding fixture, or the collected test as
unreached. A test that the configuration does not collect never runs and is reported.
