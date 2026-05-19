"""add_storefront_to_provider_accounts

Revision ID: 004_storefront
Revises: 1e223c758a44
Create Date: 2026-05-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_storefront"
down_revision: Union[str, Sequence[str], None] = "1e223c758a44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("provider_accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("storefront", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("provider_accounts", schema=None) as batch_op:
        batch_op.drop_column("storefront")
