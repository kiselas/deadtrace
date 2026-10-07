project = "shop"


def skip_private(app, what, name, obj, skip, options):
    return skip or name.startswith("_")


def setup(app):
    app.connect("autodoc-skip-member", skip_private)
