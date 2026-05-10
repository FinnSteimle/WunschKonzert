"""add_replay_to_feedbacktype_enum

Revision ID: 1e223c758a44
Revises: 003_oauth_state_nonces
Create Date: 2026-05-08 11:24:28.043244

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1e223c758a44"
down_revision: Union[str, Sequence[str], None] = "003_oauth_state_nonces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 'replay' value to feedbacktype enum
    # Note: PostgreSQL doesn't support removing enum values, so downgrade will fail if data exists
    op.execute("ALTER TYPE feedbacktype ADD VALUE IF NOT EXISTS 'replay'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not support removing enum values directly
    # This would require recreating the enum type and all dependent columns
    # For safety, we leave this as a no-op
    pass
