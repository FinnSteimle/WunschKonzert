from datetime import UTC, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _db_enum(enum_cls: type[PyEnum], name: str) -> Enum:
    """Map Python enums to PostgreSQL enum values (not member names)."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda enum_values: [item.value for item in enum_values],
    )


# Enums for status fields
class AuthType(PyEnum):
    EMAIL = "email"
    GOOGLE = "google"
    SPOTIFY = "spotify"
    APPLE = "apple"


class AccountStatus(PyEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class RoomStatus(PyEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MembershipStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    KICKED = "kicked"
    BANNED = "banned"


class QueueEntryStatus(PyEnum):
    QUEUED = "queued"
    PLAYING = "playing"
    PLAYED = "played"
    SKIPPED = "skipped"
    REMOVED = "removed"


class PlaybackState(PyEnum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class ProposalStatus(PyEnum):
    OPEN = "open"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"


class FeedbackType(PyEnum):
    LIKE = "like"
    DISLIKE = "dislike"
    SKIP = "skip"


# Identity Package
class User(Base):
    # we use __tablename__ since we will maybe change the class name in the future and
    # we want the option open to do that without a migration
    __tablename__ = "users"

    # Use SQLAlchemy 2.0 Style, for better typechecks. (Removes confusing red squiggly lines)
    userId: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    displayName: Mapped[str] = mapped_column(String, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        # uselist is used, since realationship by default returns a list, if a relationship is 1-1, set it to false
        "Account",
        back_populates="user",
        uselist=False,
    )
    provider_accounts: Mapped[list["ProviderAccount"]] = relationship(
        "ProviderAccount", back_populates="user"
    )
    room_memberships: Mapped[list["RoomMembership"]] = relationship(
        "RoomMembership", back_populates="user"
    )
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="user")
    song_feedback: Mapped[list["SongFeedback"]] = relationship(
        "SongFeedback", back_populates="user"
    )
    proposal_votes: Mapped[list["ProposalVote"]] = relationship(
        "ProposalVote", back_populates="user"
    )
    queue_entries: Mapped[list["QueueEntry"]] = relationship(
        "QueueEntry", back_populates="added_by"
    )


class Account(Base):
    __tablename__ = "accounts"

    accountId: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    authType: Mapped[AuthType] = mapped_column(
        _db_enum(AuthType, "authtype"), nullable=False
    )
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), unique=True, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="account")


class MusicProvider(Base):
    __tablename__ = "music_providers"

    providerId: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Relationships
    provider_accounts: Mapped[list["ProviderAccount"]] = relationship(
        "ProviderAccount", back_populates="provider"
    )
    rooms: Mapped[list["Room"]] = relationship(
        "Room", back_populates="supported_provider"
    )


class ProviderAccount(Base):
    __tablename__ = "provider_accounts"

    providerAccountId: Mapped[str] = mapped_column(String, primary_key=True)
    externalUserId: Mapped[str] = mapped_column(String, nullable=False)
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), nullable=False
    )
    providerId: Mapped[str] = mapped_column(
        String, ForeignKey("music_providers.providerId"), nullable=False
    )
    linkedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    status: Mapped[AccountStatus] = mapped_column(
        _db_enum(AccountStatus, "accountstatus"), default=AccountStatus.ACTIVE
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="provider_accounts")
    provider: Mapped["MusicProvider"] = relationship(
        "MusicProvider", back_populates="provider_accounts"
    )


# Room Management Package
class Room(Base):
    __tablename__ = "rooms"

    roomId: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    joinCode: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[RoomStatus] = mapped_column(
        _db_enum(RoomStatus, "roomstatus"), default=RoomStatus.ACTIVE
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    hostedBy: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), nullable=False
    )
    supportedProviderId: Mapped[str] = mapped_column(
        String, ForeignKey("music_providers.providerId"), nullable=False
    )

    # Relationships
    host: Mapped["User"] = relationship("User")
    supported_provider: Mapped["MusicProvider"] = relationship(
        "MusicProvider", back_populates="rooms"
    )
    memberships: Mapped[list["RoomMembership"]] = relationship(
        "RoomMembership", back_populates="room"
    )
    queue_entries: Mapped[list["QueueEntry"]] = relationship(
        "QueueEntry", back_populates="room"
    )
    playback_sessions: Mapped[list["PlaybackSession"]] = relationship(
        "PlaybackSession", back_populates="room"
    )
    playback_history: Mapped[list["PlaybackHistoryEntry"]] = relationship(
        "PlaybackHistoryEntry", back_populates="room"
    )
    proposal_sessions: Mapped[list["ProposalVoteSession"]] = relationship(
        "ProposalVoteSession", back_populates="room"
    )


class RoomMembership(Base):
    __tablename__ = "room_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), nullable=False
    )
    roomId: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.roomId"), nullable=False
    )
    joinedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    leftAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    membershipStatus: Mapped[MembershipStatus] = mapped_column(
        _db_enum(MembershipStatus, "membershipstatus"),
        default=MembershipStatus.ACTIVE,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="room_memberships")
    room: Mapped["Room"] = relationship("Room", back_populates="memberships")
    kick_proposals: Mapped[list["KickUserProposal"]] = relationship(
        "KickUserProposal", back_populates="membership"
    )


# Queue and Playback Package
class Track(Base):
    __tablename__ = "tracks"

    trackId: Mapped[str] = mapped_column(String, primary_key=True)
    providerTrackId: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    album: Mapped[str | None] = mapped_column(String)
    duration: Mapped[int | None] = mapped_column(Integer)  # in seconds
    coverUrl: Mapped[str | None] = mapped_column(String)
    deepLink: Mapped[str | None] = mapped_column(String)

    # Relationships
    queue_entries: Mapped[list["QueueEntry"]] = relationship(
        "QueueEntry", back_populates="track"
    )


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    queueEntryId: Mapped[str] = mapped_column(String, primary_key=True)
    roomId: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.roomId"), nullable=False
    )
    trackId: Mapped[str] = mapped_column(
        String, ForeignKey("tracks.trackId"), nullable=False
    )
    addedBy: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), nullable=False
    )
    queuedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[QueueEntryStatus] = mapped_column(
        _db_enum(QueueEntryStatus, "queueentrystatus"),
        default=QueueEntryStatus.QUEUED,
    )
    voteScore: Mapped[int] = mapped_column(Integer, default=0)
    orderRank: Mapped[float] = mapped_column(Float, default=0.0)
    isCurrent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="queue_entries")
    track: Mapped["Track"] = relationship("Track", back_populates="queue_entries")
    added_by: Mapped["User"] = relationship("User", back_populates="queue_entries")
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="queue_entry"
    )
    song_feedback: Mapped[list["SongFeedback"]] = relationship(
        "SongFeedback", back_populates="queue_entry"
    )
    playback_sessions: Mapped[list["PlaybackSession"]] = relationship(
        "PlaybackSession", back_populates="queue_entry"
    )
    playback_history: Mapped[list["PlaybackHistoryEntry"]] = relationship(
        "PlaybackHistoryEntry", back_populates="queue_entry"
    )
    delete_proposals: Mapped[list["DeleteQueueEntryProposal"]] = relationship(
        "DeleteQueueEntryProposal", back_populates="queue_entry"
    )


class PlaybackSession(Base):
    __tablename__ = "playback_sessions"

    playbackSessionId: Mapped[str] = mapped_column(String, primary_key=True)
    roomId: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.roomId"), nullable=False
    )
    queueEntryId: Mapped[str] = mapped_column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    startedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    pausedAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    elapsedTime: Mapped[int] = mapped_column(Integer, default=0)  # in seconds
    state: Mapped[PlaybackState] = mapped_column(
        _db_enum(PlaybackState, "playbackstate"), default=PlaybackState.STOPPED
    )

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="playback_sessions")
    queue_entry: Mapped["QueueEntry"] = relationship(
        "QueueEntry", back_populates="playback_sessions"
    )
    skip_proposals: Mapped[list["SkipProposal"]] = relationship(
        "SkipProposal", back_populates="playback_session"
    )


class PlaybackHistoryEntry(Base):
    __tablename__ = "playback_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roomId: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.roomId"), nullable=False
    )
    queueEntryId: Mapped[str] = mapped_column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    playedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    replayCount: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="playback_history")
    queue_entry: Mapped["QueueEntry"] = relationship(
        "QueueEntry", back_populates="playback_history"
    )
    replay_proposals: Mapped[list["ReplayProposal"]] = relationship(
        "ReplayProposal", back_populates="history_entry"
    )


# Interaction Package
class Comment(Base):
    __tablename__ = "comments"

    commentId: Mapped[str] = mapped_column(String, primary_key=True)
    queueEntryId: Mapped[str] = mapped_column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), nullable=False
    )
    text: Mapped[str] = mapped_column(String, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    queue_entry: Mapped["QueueEntry"] = relationship(
        "QueueEntry", back_populates="comments"
    )
    user: Mapped["User"] = relationship("User", back_populates="comments")


class SongFeedback(Base):
    __tablename__ = "song_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    queueEntryId: Mapped[str] = mapped_column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), nullable=False
    )
    votedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    type: Mapped[FeedbackType] = mapped_column(
        _db_enum(FeedbackType, "feedbacktype"), nullable=False
    )

    # Relationships
    queue_entry: Mapped["QueueEntry"] = relationship(
        "QueueEntry", back_populates="song_feedback"
    )
    user: Mapped["User"] = relationship("User", back_populates="song_feedback")


# Room Voting Package
class ProposalVoteSession(Base):
    __tablename__ = "proposal_vote_sessions"

    proposalId: Mapped[str] = mapped_column(String, primary_key=True)
    roomId: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.roomId"), nullable=False
    )
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    threshold: Mapped[float] = mapped_column(
        Float, default=0.5
    )  # Percentage needed to pass
    status: Mapped[ProposalStatus] = mapped_column(
        _db_enum(ProposalStatus, "proposalstatus"), default=ProposalStatus.OPEN
    )

    # Discriminator for inheritance
    type: Mapped[str | None] = mapped_column(String(50))

    # we use single table inheritance
    # sqlalchemy uses __mapper_args__ to make sure the correct type when querying things from database
    __mapper_args__ = {
        "polymorphic_identity": "proposal_vote_session",
        "polymorphic_on": type,
    }

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="proposal_sessions")
    votes: Mapped[list["ProposalVote"]] = relationship(
        "ProposalVote", back_populates="proposal_session"
    )


class SkipProposal(ProposalVoteSession):
    __tablename__ = "skip_proposals"

    proposalId: Mapped[str] = mapped_column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    playbackSessionId: Mapped[str] = mapped_column(
        String, ForeignKey("playback_sessions.playbackSessionId"), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_identity": "skip_proposal",
    }

    # Relationships
    playback_session: Mapped["PlaybackSession"] = relationship(
        "PlaybackSession", back_populates="skip_proposals"
    )


class ReplayProposal(ProposalVoteSession):
    __tablename__ = "replay_proposals"

    proposalId: Mapped[str] = mapped_column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    historyEntryId: Mapped[int] = mapped_column(
        Integer, ForeignKey("playback_history.id"), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_identity": "replay_proposal",
    }

    # Relationships
    history_entry: Mapped["PlaybackHistoryEntry"] = relationship(
        "PlaybackHistoryEntry", back_populates="replay_proposals"
    )


class DeleteQueueEntryProposal(ProposalVoteSession):
    __tablename__ = "delete_queue_entry_proposals"

    proposalId: Mapped[str] = mapped_column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    queueEntryId: Mapped[str] = mapped_column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_identity": "delete_queue_entry_proposal",
    }

    # Relationships
    queue_entry: Mapped["QueueEntry"] = relationship(
        "QueueEntry", back_populates="delete_proposals"
    )


class KickUserProposal(ProposalVoteSession):
    __tablename__ = "kick_user_proposals"

    proposalId: Mapped[str] = mapped_column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    membershipId: Mapped[int] = mapped_column(
        Integer, ForeignKey("room_memberships.id"), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_identity": "kick_user_proposal",
    }

    # Relationships
    membership: Mapped["RoomMembership"] = relationship(
        "RoomMembership", back_populates="kick_proposals"
    )


class ProposalVote(Base):
    __tablename__ = "proposal_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposalId: Mapped[str] = mapped_column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), nullable=False
    )
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("users.userId"), nullable=False
    )
    votedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Relationships
    proposal_session: Mapped["ProposalVoteSession"] = relationship(
        "ProposalVoteSession", back_populates="votes"
    )
    user: Mapped["User"] = relationship("User", back_populates="proposal_votes")
