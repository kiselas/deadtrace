# Django automatic worlds

The project configures no world. Its settings module defines `INSTALLED_APPS`, so it is the root
of an automatic `production:django` world, `manage.py` is the root of `production:scripts`, and
the project is an application rather than a library, so its public names are not roots.

`manage.py` points `DJANGO_SETTINGS_MODULE` at `mysite.settings`, whose `INSTALLED_APPS`
lists `polls` through its `AppConfig` and `blog` by package. When Django starts it imports
the `models` module of every installed application and, with `django.contrib.admin`
installed, its `admin` module; `manage.py closepoll` loads
`polls.management.commands.closepoll` and instantiates its `Command`; `{% load poll_extras %}`
imports the template-tag library; and the server imports the module that
`WSGI_APPLICATION` names. No project code imports any of them, so reporting
`QuestionAdmin.get_queryset`, `Command.handle`, `close_all`, `shout`, `Post.published`, or
`configure_monitoring` as unreached is unsafe; views and models reached through the URL
configuration stay protected too. `unused_model_helper`, `unused_view`, `unused_util`, and
`blog.drafts.unused_draft` are never called or loaded and must stay candidates.
