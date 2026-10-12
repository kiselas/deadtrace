def pytest_configure():
    from django.conf import settings

    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "tests"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3"}},
    )
