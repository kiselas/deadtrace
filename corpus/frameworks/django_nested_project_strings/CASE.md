# A Django project in a subdirectory names its modules from there

`site/manage.py` runs with `site/` as the working directory, so the settings say
`ROOT_URLCONF = "shop_app.urls"` for the module `site/shop_app/urls.py`. The string names that
unique nested package: the URL configuration is used and routes `home`. `INSTALLED_APPS` lists
`"blog"`, the package `site/blog`, so Django imports its `admin` module and registers `PostAdmin`. `unused_view` is routed
nowhere.
