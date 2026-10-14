# Cookiecutter selects local extensions by manifest names

Cookiecutter's documented `_extensions` array imports each named extension from
the template directory. A function decorated with `cookiecutter.utils.simple_filter`
becomes a Jinja extension whose filter invokes that function. This is an external
execution root even when the project has no Python call to it.

The manifest under `a/` names a filter, an extension class and a filter reexported
by a regular package. The selected filter and its helper, class and its public
method, and reexported filter must not be candidates. Identically named code
under `b/` is a separate template and remains unused. Unlisted neighboring helpers
remain candidates; listing one extension must not expose the whole module.

Independent specification: https://cookiecutter.readthedocs.io/en/stable/advanced/local_extensions.html
and Cookiecutter v2.7.1 `cookiecutter/utils.py` (`simple_filter`).
These files are syntax data; the scanner must never load Cookiecutter or run them.
