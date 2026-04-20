"""add_oauth_state_nonces

Revision ID: 003_oauth_state_nonces
Revises: 002_oauth_tokens
Create Date: 2026-04-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_oauth_state_nonces"
down_revision: Union[str, Sequence[str], None] = "002_oauth_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_state_nonces",
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("providerId", sa.String(), nullable=False),
        sa.Column("issuedAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumedAt", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("nonce"),
    )
    with op.batch_alter_table("oauth_state_nonces", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_oauth_state_nonces_providerId"), ["providerId"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_oauth_state_nonces_expiresAt"), ["expiresAt"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("oauth_state_nonces", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_state_nonces_expiresAt"))
        batch_op.drop_index(batch_op.f("ix_oauth_state_nonces_providerId"))
    op.drop_table("oauth_state_nonces")
