# Django applications installed by settings.configure in a conftest

A reusable Django package tests itself without a settings module: `pytest_configure` in
`tests/conftest.py` calls `settings.configure(INSTALLED_APPS=[..., "tests"])`. Django then imports
`tests.models` and registers `Anchor`, which is not a candidate. `_helper` is called by nothing.
