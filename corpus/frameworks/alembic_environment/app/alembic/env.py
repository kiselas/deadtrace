from alembic import context


def run_migrations_online() -> None:
    context.run_migrations()


run_migrations_online()
