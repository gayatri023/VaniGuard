"""events are append-only at the database level

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

from vani.db import guard_statements

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT COUNT(*) FROM delete_gate")).scalar() == 0:
        conn.execute(sa.text("INSERT INTO delete_gate (id, allow) VALUES (1, 0)"))
    for stmt in guard_statements(conn.dialect.name):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS events_guard ON events")
        op.execute("DROP FUNCTION IF EXISTS vani_events_guard()")
    else:
        op.execute("DROP TRIGGER IF EXISTS events_no_update")
        op.execute("DROP TRIGGER IF EXISTS events_no_delete")
