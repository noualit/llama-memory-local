import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# Use DATABASE_URL from app settings if available; otherwise fall back to env.
try:
    from app.settings import settings
    db_url = settings.DATABASE_URL
except Exception:
    db_url = os.getenv("DATABASE_URL", "")

if db_url:
    # Override sqlalchemy.url in alembic.ini with real DATABASE_URL
    config.set_main_option("sqlalchemy.url", db_url)

# Read logging config from alembic.ini (if exists)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # We manage schema via raw SQL migrations.


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
