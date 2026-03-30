from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


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
    __tablename__ = "users"

    userId = Column(String, primary_key=True, index=True)
    displayName = Column(String, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    # Relationships
    account = relationship("Account", back_populates="user", uselist=False)
    provider_accounts = relationship("ProviderAccount", back_populates="user")
    room_memberships = relationship("RoomMembership", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    song_feedback = relationship("SongFeedback", back_populates="user")
    proposal_votes = relationship("ProposalVote", back_populates="user")
    queue_entries = relationship("QueueEntry", back_populates="added_by")


class Account(Base):
    __tablename__ = "accounts"

    accountId = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    authType = Column(_db_enum(AuthType, "authtype"), nullable=False)
    userId = Column(String, ForeignKey("users.userId"), unique=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="account")


class MusicProvider(Base):
    __tablename__ = "music_providers"

    providerId = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    # Relationships
    provider_accounts = relationship("ProviderAccount", back_populates="provider")
    rooms = relationship("Room", back_populates="supported_provider")


class ProviderAccount(Base):
    __tablename__ = "provider_accounts"

    providerAccountId = Column(String, primary_key=True)
    externalUserId = Column(String, nullable=False)
    userId = Column(String, ForeignKey("users.userId"), nullable=False)
    providerId = Column(
        String, ForeignKey("music_providers.providerId"), nullable=False
    )
    linkedAt = Column(DateTime, default=datetime.utcnow)
    status = Column(_db_enum(AccountStatus, "accountstatus"), default=AccountStatus.ACTIVE)

    # Relationships
    user = relationship("User", back_populates="provider_accounts")
    provider = relationship("MusicProvider", back_populates="provider_accounts")


# Room Management Package
class Room(Base):
    __tablename__ = "rooms"

    roomId = Column(String, primary_key=True, index=True)
    joinCode = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    status = Column(_db_enum(RoomStatus, "roomstatus"), default=RoomStatus.ACTIVE)
    createdAt = Column(DateTime, default=datetime.utcnow)
    hostedBy = Column(String, ForeignKey("users.userId"), nullable=False)
    supportedProviderId = Column(
        String, ForeignKey("music_providers.providerId"), nullable=False
    )

    # Relationships
    host = relationship("User")
    supported_provider = relationship("MusicProvider", back_populates="rooms")
    memberships = relationship("RoomMembership", back_populates="room")
    queue_entries = relationship("QueueEntry", back_populates="room")
    playback_sessions = relationship("PlaybackSession", back_populates="room")
    playback_history = relationship("PlaybackHistoryEntry", back_populates="room")
    proposal_sessions = relationship("ProposalVoteSession", back_populates="room")


class RoomMembership(Base):
    __tablename__ = "room_memberships"

    id = Column(Integer, primary_key=True)
    userId = Column(String, ForeignKey("users.userId"), nullable=False)
    roomId = Column(String, ForeignKey("rooms.roomId"), nullable=False)
    joinedAt = Column(DateTime, default=datetime.utcnow)
    leftAt = Column(DateTime, nullable=True)
    membershipStatus = Column(
        _db_enum(MembershipStatus, "membershipstatus"),
        default=MembershipStatus.ACTIVE,
    )

    # Relationships
    user = relationship("User", back_populates="room_memberships")
    room = relationship("Room", back_populates="memberships")
    kick_proposals = relationship("KickUserProposal", back_populates="membership")


# Queue and Playback Package
class Track(Base):
    __tablename__ = "tracks"

    trackId = Column(String, primary_key=True)
    providerTrackId = Column(String, nullable=False)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    album = Column(String)
    duration = Column(Integer)  # in seconds
    coverUrl = Column(String)
    deepLink = Column(String)

    # Relationships
    queue_entries = relationship("QueueEntry", back_populates="track")


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    queueEntryId = Column(String, primary_key=True)
    roomId = Column(String, ForeignKey("rooms.roomId"), nullable=False)
    trackId = Column(String, ForeignKey("tracks.trackId"), nullable=False)
    addedBy = Column(String, ForeignKey("users.userId"), nullable=False)
    queuedAt = Column(DateTime, default=datetime.utcnow)
    position = Column(Integer, nullable=False)
    status = Column(
        _db_enum(QueueEntryStatus, "queueentrystatus"),
        default=QueueEntryStatus.QUEUED,
    )
    voteScore = Column(Integer, default=0)
    orderRank = Column(Float, default=0.0)
    isCurrent = Column(Boolean, default=False)

    # Relationships
    room = relationship("Room", back_populates="queue_entries")
    track = relationship("Track", back_populates="queue_entries")
    added_by = relationship("User", back_populates="queue_entries")
    comments = relationship("Comment", back_populates="queue_entry")
    song_feedback = relationship("SongFeedback", back_populates="queue_entry")
    playback_sessions = relationship("PlaybackSession", back_populates="queue_entry")
    playback_history = relationship(
        "PlaybackHistoryEntry", back_populates="queue_entry"
    )
    delete_proposals = relationship(
        "DeleteQueueEntryProposal", back_populates="queue_entry"
    )


class PlaybackSession(Base):
    __tablename__ = "playback_sessions"

    playbackSessionId = Column(String, primary_key=True)
    roomId = Column(String, ForeignKey("rooms.roomId"), nullable=False)
    queueEntryId = Column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    startedAt = Column(DateTime, default=datetime.utcnow)
    pausedAt = Column(DateTime, nullable=True)
    elapsedTime = Column(Integer, default=0)  # in seconds
    state = Column(_db_enum(PlaybackState, "playbackstate"), default=PlaybackState.STOPPED)

    # Relationships
    room = relationship("Room", back_populates="playback_sessions")
    queue_entry = relationship("QueueEntry", back_populates="playback_sessions")
    skip_proposals = relationship("SkipProposal", back_populates="playback_session")


class PlaybackHistoryEntry(Base):
    __tablename__ = "playback_history"

    id = Column(Integer, primary_key=True)
    roomId = Column(String, ForeignKey("rooms.roomId"), nullable=False)
    queueEntryId = Column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    playedAt = Column(DateTime, default=datetime.utcnow)
    replayCount = Column(Integer, default=1)

    # Relationships
    room = relationship("Room", back_populates="playback_history")
    queue_entry = relationship("QueueEntry", back_populates="playback_history")
    replay_proposals = relationship("ReplayProposal", back_populates="history_entry")


# Interaction Package
class Comment(Base):
    __tablename__ = "comments"

    commentId = Column(String, primary_key=True)
    queueEntryId = Column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    userId = Column(String, ForeignKey("users.userId"), nullable=False)
    text = Column(String, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)

    # Relationships
    queue_entry = relationship("QueueEntry", back_populates="comments")
    user = relationship("User", back_populates="comments")


class SongFeedback(Base):
    __tablename__ = "song_feedback"

    id = Column(Integer, primary_key=True)
    queueEntryId = Column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )
    userId = Column(String, ForeignKey("users.userId"), nullable=False)
    votedAt = Column(DateTime, default=datetime.utcnow)
    type = Column(_db_enum(FeedbackType, "feedbacktype"), nullable=False)

    # Relationships
    queue_entry = relationship("QueueEntry", back_populates="song_feedback")
    user = relationship("User", back_populates="song_feedback")


# Room Voting Package
class ProposalVoteSession(Base):
    __tablename__ = "proposal_vote_sessions"

    proposalId = Column(String, primary_key=True)
    roomId = Column(String, ForeignKey("rooms.roomId"), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow)
    expiresAt = Column(DateTime, nullable=False)
    threshold = Column(Float, default=0.5)  # Percentage needed to pass
    status = Column(_db_enum(ProposalStatus, "proposalstatus"), default=ProposalStatus.OPEN)

    # Discriminator for inheritance
    type = Column(String(50))

    __mapper_args__ = {
        "polymorphic_identity": "proposal_vote_session",
        "polymorphic_on": type,
    }

    # Relationships
    room = relationship("Room", back_populates="proposal_sessions")
    votes = relationship("ProposalVote", back_populates="proposal_session")


class SkipProposal(ProposalVoteSession):
    __tablename__ = "skip_proposals"

    proposalId = Column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    playbackSessionId = Column(
        String, ForeignKey("playback_sessions.playbackSessionId"), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_identity": "skip_proposal",
    }

    # Relationships
    playback_session = relationship("PlaybackSession", back_populates="skip_proposals")


class ReplayProposal(ProposalVoteSession):
    __tablename__ = "replay_proposals"

    proposalId = Column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    historyEntryId = Column(Integer, ForeignKey("playback_history.id"), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": "replay_proposal",
    }

    # Relationships
    history_entry = relationship(
        "PlaybackHistoryEntry", back_populates="replay_proposals"
    )


class DeleteQueueEntryProposal(ProposalVoteSession):
    __tablename__ = "delete_queue_entry_proposals"

    proposalId = Column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    queueEntryId = Column(
        String, ForeignKey("queue_entries.queueEntryId"), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_identity": "delete_queue_entry_proposal",
    }

    # Relationships
    queue_entry = relationship("QueueEntry", back_populates="delete_proposals")


class KickUserProposal(ProposalVoteSession):
    __tablename__ = "kick_user_proposals"

    proposalId = Column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), primary_key=True
    )
    membershipId = Column(Integer, ForeignKey("room_memberships.id"), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": "kick_user_proposal",
    }

    # Relationships
    membership = relationship("RoomMembership", back_populates="kick_proposals")


class ProposalVote(Base):
    __tablename__ = "proposal_votes"

    id = Column(Integer, primary_key=True)
    proposalId = Column(
        String, ForeignKey("proposal_vote_sessions.proposalId"), nullable=False
    )
    userId = Column(String, ForeignKey("users.userId"), nullable=False)
    votedAt = Column(DateTime, default=datetime.utcnow)

    # Relationships
    proposal_session = relationship("ProposalVoteSession", back_populates="votes")
    user = relationship("User", back_populates="proposal_votes")
