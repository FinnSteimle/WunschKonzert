"""add_provider_account_oauth_tokens

Revision ID: 002_oauth_tokens
Revises: 47fe690853d6
Create Date: 2026-04-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_oauth_tokens"
down_revision: Union[str, Sequence[str], None] = "47fe690853d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("provider_accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("accessToken", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("refreshToken", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("tokenExpiresAt", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("provider_accounts", schema=None) as batch_op:
        batch_op.drop_column("tokenExpiresAt")
        batch_op.drop_column("refreshToken")
        batch_op.drop_column("accessToken")
