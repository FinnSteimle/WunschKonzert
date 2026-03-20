"""Initial database schema

Revision ID: 001_initial
Revises:
Create Date: 2024-03-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Identity Package
    op.create_table(
        "users",
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("displayName", sa.String(), nullable=False),
        sa.Column("createdAt", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("userId"),
    )
    op.create_table(
        "accounts",
        sa.Column("accountId", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column(
            "authType",
            sa.Enum("email", "google", "spotify", "apple", name="authtype"),
            nullable=False,
        ),
        sa.Column("userId", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["userId"],
            ["users.userId"],
        ),
        sa.PrimaryKeyConstraint("accountId"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("userId"),
    )
    op.create_table(
        "music_providers",
        sa.Column("providerId", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("providerId"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "provider_accounts",
        sa.Column("providerAccountId", sa.String(), nullable=False),
        sa.Column("externalUserId", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("providerId", sa.String(), nullable=False),
        sa.Column("linkedAt", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", "deleted", name="accountstatus"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["providerId"],
            ["music_providers.providerId"],
        ),
        sa.ForeignKeyConstraint(
            ["userId"],
            ["users.userId"],
        ),
        sa.PrimaryKeyConstraint("providerAccountId"),
    )

    # Room Management Package
    op.create_table(
        "rooms",
        sa.Column("roomId", sa.String(), nullable=False),
        sa.Column("joinCode", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "archived", "deleted", name="roomstatus"),
            nullable=True,
        ),
        sa.Column("createdAt", sa.DateTime(), nullable=True),
        sa.Column("hostedBy", sa.String(), nullable=False),
        sa.Column("supportedProviderId", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hostedBy"],
            ["users.userId"],
        ),
        sa.ForeignKeyConstraint(
            ["supportedProviderId"],
            ["music_providers.providerId"],
        ),
        sa.PrimaryKeyConstraint("roomId"),
        sa.UniqueConstraint("joinCode"),
    )
    op.create_table(
        "room_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("roomId", sa.String(), nullable=False),
        sa.Column("joinedAt", sa.DateTime(), nullable=True),
        sa.Column("leftAt", sa.DateTime(), nullable=True),
        sa.Column(
            "membershipStatus",
            sa.Enum("active", "inactive", "kicked", "banned", name="membershipstatus"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["roomId"],
            ["rooms.roomId"],
        ),
        sa.ForeignKeyConstraint(
            ["userId"],
            ["users.userId"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Queue and Playback Package
    op.create_table(
        "tracks",
        sa.Column("trackId", sa.String(), nullable=False),
        sa.Column("providerTrackId", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("artist", sa.String(), nullable=False),
        sa.Column("album", sa.String(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("coverUrl", sa.String(), nullable=True),
        sa.Column("deepLink", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("trackId"),
    )
    op.create_table(
        "queue_entries",
        sa.Column("queueEntryId", sa.String(), nullable=False),
        sa.Column("roomId", sa.String(), nullable=False),
        sa.Column("trackId", sa.String(), nullable=False),
        sa.Column("addedBy", sa.String(), nullable=False),
        sa.Column("queuedAt", sa.DateTime(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "playing",
                "played",
                "skipped",
                "removed",
                name="queueentrystatus",
            ),
            nullable=True,
        ),
        sa.Column("voteScore", sa.Integer(), nullable=True),
        sa.Column("orderRank", sa.Float(), nullable=True),
        sa.Column("isCurrent", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["addedBy"],
            ["users.userId"],
        ),
        sa.ForeignKeyConstraint(
            ["roomId"],
            ["rooms.roomId"],
        ),
        sa.ForeignKeyConstraint(
            ["trackId"],
            ["tracks.trackId"],
        ),
        sa.PrimaryKeyConstraint("queueEntryId"),
    )
    op.create_table(
        "playback_sessions",
        sa.Column("playbackSessionId", sa.String(), nullable=False),
        sa.Column("roomId", sa.String(), nullable=False),
        sa.Column("queueEntryId", sa.String(), nullable=False),
        sa.Column("startedAt", sa.DateTime(), nullable=True),
        sa.Column("pausedAt", sa.DateTime(), nullable=True),
        sa.Column("elapsedTime", sa.Integer(), nullable=True),
        sa.Column(
            "state",
            sa.Enum("playing", "paused", "stopped", name="playbackstate"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["queueEntryId"],
            ["queue_entries.queueEntryId"],
        ),
        sa.ForeignKeyConstraint(
            ["roomId"],
            ["rooms.roomId"],
        ),
        sa.PrimaryKeyConstraint("playbackSessionId"),
    )
    op.create_table(
        "playback_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("roomId", sa.String(), nullable=False),
        sa.Column("queueEntryId", sa.String(), nullable=False),
        sa.Column("playedAt", sa.DateTime(), nullable=True),
        sa.Column("replayCount", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["queueEntryId"],
            ["queue_entries.queueEntryId"],
        ),
        sa.ForeignKeyConstraint(
            ["roomId"],
            ["rooms.roomId"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Interaction Package
    op.create_table(
        "comments",
        sa.Column("commentId", sa.String(), nullable=False),
        sa.Column("queueEntryId", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("createdAt", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["queueEntryId"],
            ["queue_entries.queueEntryId"],
        ),
        sa.ForeignKeyConstraint(
            ["userId"],
            ["users.userId"],
        ),
        sa.PrimaryKeyConstraint("commentId"),
    )
    op.create_table(
        "song_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("queueEntryId", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("votedAt", sa.DateTime(), nullable=True),
        sa.Column(
            "type",
            sa.Enum("like", "dislike", "skip", name="feedbacktype"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["queueEntryId"],
            ["queue_entries.queueEntryId"],
        ),
        sa.ForeignKeyConstraint(
            ["userId"],
            ["users.userId"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Room Voting Package
    op.create_table(
        "proposal_vote_sessions",
        sa.Column("proposalId", sa.String(), nullable=False),
        sa.Column("roomId", sa.String(), nullable=False),
        sa.Column("createdAt", sa.DateTime(), nullable=True),
        sa.Column("expiresAt", sa.DateTime(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "passed", "failed", "expired", name="proposalstatus"),
            nullable=True,
        ),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["roomId"],
            ["rooms.roomId"],
        ),
        sa.PrimaryKeyConstraint("proposalId"),
    )
    op.create_table(
        "skip_proposals",
        sa.Column("proposalId", sa.String(), nullable=False),
        sa.Column("playbackSessionId", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["playbackSessionId"],
            ["playback_sessions.playbackSessionId"],
        ),
        sa.ForeignKeyConstraint(
            ["proposalId"],
            ["proposal_vote_sessions.proposalId"],
        ),
        sa.PrimaryKeyConstraint("proposalId"),
    )
    op.create_table(
        "replay_proposals",
        sa.Column("proposalId", sa.String(), nullable=False),
        sa.Column("historyEntryId", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["historyEntryId"],
            ["playback_history.id"],
        ),
        sa.ForeignKeyConstraint(
            ["proposalId"],
            ["proposal_vote_sessions.proposalId"],
        ),
        sa.PrimaryKeyConstraint("proposalId"),
    )
    op.create_table(
        "delete_queue_entry_proposals",
        sa.Column("proposalId", sa.String(), nullable=False),
        sa.Column("queueEntryId", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["queueEntryId"],
            ["queue_entries.queueEntryId"],
        ),
        sa.ForeignKeyConstraint(
            ["proposalId"],
            ["proposal_vote_sessions.proposalId"],
        ),
        sa.PrimaryKeyConstraint("proposalId"),
    )
    op.create_table(
        "kick_user_proposals",
        sa.Column("proposalId", sa.String(), nullable=False),
        sa.Column("membershipId", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["membershipId"],
            ["room_memberships.id"],
        ),
        sa.ForeignKeyConstraint(
            ["proposalId"],
            ["proposal_vote_sessions.proposalId"],
        ),
        sa.PrimaryKeyConstraint("proposalId"),
    )
    op.create_table(
        "proposal_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proposalId", sa.String(), nullable=False),
        sa.Column("userId", sa.String(), nullable=False),
        sa.Column("votedAt", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["proposalId"],
            ["proposal_vote_sessions.proposalId"],
        ),
        sa.ForeignKeyConstraint(
            ["userId"],
            ["users.userId"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table("proposal_votes")
    op.drop_table("kick_user_proposals")
    op.drop_table("delete_queue_entry_proposals")
    op.drop_table("replay_proposals")
    op.drop_table("skip_proposals")
    op.drop_table("proposal_vote_sessions")
    op.drop_table("song_feedback")
    op.drop_table("comments")
    op.drop_table("playback_history")
    op.drop_table("playback_sessions")
    op.drop_table("queue_entries")
    op.drop_table("tracks")
    op.drop_table("room_memberships")
    op.drop_table("rooms")
    op.drop_table("provider_accounts")
    op.drop_table("music_providers")
    op.drop_table("accounts")
    op.drop_table("users")
