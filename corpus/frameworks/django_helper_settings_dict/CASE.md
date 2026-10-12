# Django applications installed by a test helper's settings

`cms_helper.py` follows the djangocms-helper convention: `HELPER_SETTINGS = dict(INSTALLED_APPS=[...])`
names the test application `tests.media_app`, and the helper's runner configures Django with it.
Django imports `tests.media_app.models` and registers `Vimeo`, which is not a candidate. `_helper` is
called by nothing.
