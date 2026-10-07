# Modules that development tools run

nox runs `noxfile.py` and calls its sessions, Sphinx runs `docs/conf.py` and calls `setup(app)`, and
mkdocs imports the hook files that `mkdocs.yml` lists. Their functions and the helpers they call are
used: `uv_sync`, `tests`, `setup`, `skip_private`, `on_page_markdown`. `unused` is referenced nowhere.
