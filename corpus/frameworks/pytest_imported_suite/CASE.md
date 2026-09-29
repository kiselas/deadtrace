# A suite imported into another test module

`tests/suite/test_pages.py` holds a test function and a test class that request the fixture
`base_url`. `tests/suite_shared/test_shared_pages.py` repeats the suite with
`from tests.suite.test_pages import *`; pytest collects the imported function and class in that
module, so they resolve `base_url` from the conftest of `tests/suite_shared`, which overrides
the fixture of `tests/suite`.

Both `base_url` fixtures run. The unsafe outcome is reporting the override: the shared conftest
is the only place the imported tests see it. A fixture that neither directory requests is still
reported.
