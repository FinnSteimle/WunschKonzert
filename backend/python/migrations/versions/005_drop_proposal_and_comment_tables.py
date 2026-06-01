"""drop_proposal_and_comment_tables

Revision ID: 005_drop_dead_tables
Revises: 004_storefront
Create Date: 2026-05-27

Removes the proposal voting subsystem and the comments table. These tables
were never wired into the application; the corresponding ORM classes have
been deleted from models/domain.py.

"""

from typing import Sequence, Union

from alembic import op

revision: str = "005_drop_dead_tables"
down_revision: Union[str, Sequence[str], None] = "004_storefront"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("proposal_votes")
    op.drop_table("skip_proposals")
    op.drop_table("replay_proposals")
    op.drop_table("delete_queue_entry_proposals")
    op.drop_table("kick_user_proposals")
    op.drop_table("proposal_vote_sessions")
    op.drop_table("comments")
    op.execute("DROP TYPE IF EXISTS proposalstatus")


def downgrade() -> None:
    # Restoring six unused tables is not worth the schema fidelity; the
    # original DDL is preserved in migration 001 for reference.
    pass
