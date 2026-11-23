import os

from alembic import context
from sqlalchemy import create_engine

from vani.db import Base

config = context.config
target_metadata = Base.metadata


def url() -> str:
    return os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url") or "sqlite:///./vani.db"


def run_migrations_online() -> None:
    engine = create_engine(url())
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=url().startswith("sqlite"))
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
