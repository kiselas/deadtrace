# Alembic environment and revisions

Alembic executes `env.py` by path and calls the `upgrade` and `downgrade` functions of the
revision scripts in the `versions` directory beside it. They are external execution contracts;
the application never imports them.

The unsafe outcome is reporting the environment's functions or a revision's `upgrade` and
`downgrade` as unreached. A helper in a revision script that nothing calls is still reported.
