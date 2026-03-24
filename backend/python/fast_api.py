import base64
import json
import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from database import (
    FeedbackType,
    MembershipStatus,
    MusicProvider,
    PlaybackSession,
    PlaybackState,
    QueueEntry,
    QueueEntryStatus,
    Room as DbRoom,
    RoomMembership,
    RoomStatus,
    SongFeedback,
    Track as DbTrack,
    User,
)
from db_utils import (
    _get_session_factory,
    check_db_health as db_check_db_health,
    create_provider_account as db_create_provider_account,
    create_room as db_create_room,
    create_room_membership as db_create_room_membership,
    create_user as db_create_user,
    get_room as db_get_room,
    get_room_by_join_code as db_get_room_by_join_code,
    get_user as db_get_user,
)
from db_utils import leave_room as db_leave_room
from models import (
    AddMusicProviderRequest,
    AddMusicProviderResponse,
    AuthRequest,
    AuthResponse,
    CreateRoomRequest,
    DeleteRoomRequest,
    PlaybackRequest,
    RoomRequest,
    RoomResponse,
    Track,
    VoteRequest,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

active_room_connections: dict[str, set[WebSocket]] = defaultdict(set)
generic_connections: set[WebSocket] = set()
room_state_cache: dict[str, dict] = {}
spotify_token_cache: dict[str, str | datetime | None] = {"token": None, "expires_at": None}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _enum_value(value: object) -> str:
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)


def _feedback_to_ui(feedback_type: FeedbackType) -> str:
    return "upvote" if feedback_type == FeedbackType.LIKE else "downvote"


def _ui_to_feedback(vote_type: str) -> FeedbackType | None:
    if vote_type == "upvote":
        return FeedbackType.LIKE
    if vote_type == "downvote":
        return FeedbackType.DISLIKE
    return None


async def ensure_provider_exists(provider_id: str) -> None:
    session_factory = _get_session_factory()
    async with session_factory() as session:
        provider = await session.get(MusicProvider, provider_id)
        if provider:
            return

        provider = MusicProvider(
            providerId=provider_id,
            name=provider_id.capitalize(),
        )
        session.add(provider)
        await session.commit()


async def ensure_active_membership(user_id: str, room_id: str) -> None:
    session_factory = _get_session_factory()
    async with session_factory() as session:
        membership = (
            await session.execute(
                select(RoomMembership).where(
                    RoomMembership.userId == user_id,
                    RoomMembership.roomId == room_id,
                )
            )
        ).scalar_one_or_none()

        if not membership:
            await db_create_room_membership(user_id, room_id)
            return

        membership.membershipStatus = MembershipStatus.ACTIVE
        membership.leftAt = None
        await session.commit()


async def _build_room_state(room_id: str) -> dict | None:
    session_factory = _get_session_factory()
    async with session_factory() as session:
        room = await session.get(DbRoom, room_id)
        if not room:
            return None

        host = await session.get(User, room.hostedBy)
        if not host:
            return None

        memberships = (
            await session.execute(
                select(RoomMembership, User)
                .join(User, RoomMembership.userId == User.userId)
                .where(
                    RoomMembership.roomId == room_id,
                    RoomMembership.membershipStatus == MembershipStatus.ACTIVE,
                    RoomMembership.leftAt.is_(None),
                )
                .order_by(RoomMembership.joinedAt.asc())
            )
        ).all()

        users: list[dict] = [
            {
                "user": {
                    "userId": host.userId,
                    "displayName": host.displayName,
                    "createdAt": host.createdAt.isoformat(),
                },
                "membership": {
                    "joinedAt": room.createdAt.isoformat(),
                    "leftAt": None,
                    "membershipStatus": "active",
                },
            }
        ]
        seen_user_ids = {host.userId}
        for membership, user in memberships:
            if user.userId in seen_user_ids:
                continue
            seen_user_ids.add(user.userId)
            users.append(
                {
                    "user": {
                        "userId": user.userId,
                        "displayName": user.displayName,
                        "createdAt": user.createdAt.isoformat(),
                    },
                    "membership": {
                        "joinedAt": membership.joinedAt.isoformat(),
                        "leftAt": membership.leftAt.isoformat() if membership.leftAt else None,
                        "membershipStatus": _enum_value(membership.membershipStatus),
                    },
                }
            )

        queue_rows = (
            await session.execute(
                select(QueueEntry, DbTrack, User)
                .join(DbTrack, QueueEntry.trackId == DbTrack.trackId)
                .join(User, QueueEntry.addedBy == User.userId)
                .where(QueueEntry.roomId == room_id)
                .where(
                    QueueEntry.status.in_(
                        [QueueEntryStatus.QUEUED, QueueEntryStatus.PLAYING, QueueEntryStatus.PLAYED]
                    )
                )
                .order_by(QueueEntry.position.asc())
            )
        ).all()

        queue_entry_ids = [row[0].queueEntryId for row in queue_rows]
        feedback_map: dict[str, list[SongFeedback]] = {entry_id: [] for entry_id in queue_entry_ids}
        if queue_entry_ids:
            feedback_rows = (
                await session.execute(
                    select(SongFeedback).where(SongFeedback.queueEntryId.in_(queue_entry_ids))
                )
            ).scalars()
            for feedback in feedback_rows:
                feedback_map[feedback.queueEntryId].append(feedback)

        queue: list[dict] = []
        for queue_entry, track, added_by_user in queue_rows:
            feedback_entries = feedback_map.get(queue_entry.queueEntryId, [])
            upvotes = sum(1 for feedback in feedback_entries if feedback.type == FeedbackType.LIKE)
            downvotes = sum(1 for feedback in feedback_entries if feedback.type == FeedbackType.DISLIKE)
            vote_score = upvotes - downvotes
            queue.append(
                {
                    "queueEntryId": queue_entry.queueEntryId,
                    "track": {
                        "trackId": track.trackId,
                        "providerTrackId": track.providerTrackId,
                        "title": track.title,
                        "artist": track.artist,
                        "album": track.album or "",
                        "duration": track.duration or 0,
                        "coverUrl": track.coverUrl or "",
                        "deepLink": track.deepLink or "",
                    },
                    "addedBy": {
                        "userId": added_by_user.userId,
                        "displayName": added_by_user.displayName,
                    },
                    "queuedAt": queue_entry.queuedAt.isoformat(),
                    "position": queue_entry.position,
                    "status": _enum_value(queue_entry.status),
                    "voteScore": vote_score,
                    "orderRank": float(queue_entry.orderRank or queue_entry.position),
                    "feedback": [
                        {
                            "userId": feedback.userId,
                            "votedAt": feedback.votedAt.isoformat(),
                            "type": _feedback_to_ui(feedback.type),
                        }
                        for feedback in feedback_entries
                    ],
                }
            )

        queue.sort(
            key=lambda item: (
                0 if item["status"] == "playing" else 1,
                -item["voteScore"],
                item["position"],
            )
        )

        latest_playback = (
            await session.execute(
                select(PlaybackSession)
                .where(PlaybackSession.roomId == room_id)
                .order_by(PlaybackSession.startedAt.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        playback = {
            "state": "stopped",
            "currentQueueEntryId": None,
            "updatedAt": _now_iso(),
            "positionMs": 0,
        }
        if latest_playback:
            playback_state = _enum_value(latest_playback.state)
            playback = {
                "state": playback_state,
                "currentQueueEntryId": (
                    latest_playback.queueEntryId if playback_state != "stopped" else None
                ),
                "updatedAt": latest_playback.startedAt.isoformat(),
                "positionMs": int(latest_playback.elapsedTime or 0) * 1000,
            }

        state = {
            "room": {
                "roomId": room.roomId,
                "joinCode": room.joinCode,
                "name": room.name,
                "status": _enum_value(room.status),
                "createdAt": room.createdAt.isoformat(),
                "supportedProviderId": room.supportedProviderId,
            },
            "host": {
                "userId": host.userId,
                "displayName": host.displayName,
                "createdAt": host.createdAt.isoformat(),
            },
            "users": users,
            "queue": queue,
            "playback": playback,
        }

        return state


async def refresh_room_state(room_id: str, event_type: str | None = None) -> dict:
    room_state = await _build_room_state(room_id)
    if room_state is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if event_type:
        room_state["lastEvent"] = {"type": event_type, "at": _now_iso()}

    room_state_cache[room_id] = room_state
    return room_state


async def _add_to_queue(room_id: str, track_data: dict, user_id: str) -> dict:
    if not track_data:
        raise HTTPException(status_code=400, detail="No track data provided")

    track = Track(**track_data)
    session_factory = _get_session_factory()
    async with session_factory() as session:
        room = await session.get(DbRoom, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if room.status != RoomStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Room is not active")

        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        db_track = await session.get(DbTrack, track.trackId)
        if not db_track:
            db_track = DbTrack(
                trackId=track.trackId,
                providerTrackId=track.providerTrackId,
                title=track.title,
                artist=track.artist,
                album=track.album,
                duration=track.duration,
                coverUrl=track.coverUrl,
                deepLink=track.deepLink,
            )
            session.add(db_track)

        max_position = (
            await session.execute(
                select(func.max(QueueEntry.position)).where(QueueEntry.roomId == room_id)
            )
        ).scalar_one_or_none()
        next_position = int(max_position or 0) + 1

        has_playing = (
            await session.execute(
                select(QueueEntry)
                .where(QueueEntry.roomId == room_id, QueueEntry.status == QueueEntryStatus.PLAYING)
                .limit(1)
            )
        ).scalar_one_or_none()

        queue_entry_id = f"QENTRY{uuid.uuid4().hex[:8].upper()}"
        queue_entry = QueueEntry(
            queueEntryId=queue_entry_id,
            roomId=room_id,
            trackId=track.trackId,
            addedBy=user_id,
            position=next_position,
            status=QueueEntryStatus.PLAYING if has_playing is None else QueueEntryStatus.QUEUED,
            voteScore=0,
            orderRank=float(next_position),
        )
        session.add(queue_entry)
        await session.flush()

        if has_playing is None:
            playback_session = PlaybackSession(
                playbackSessionId=str(uuid.uuid4()),
                roomId=room_id,
                queueEntryId=queue_entry_id,
                state=PlaybackState.PLAYING,
                elapsedTime=0,
            )
            session.add(playback_session)

        await session.commit()

    return await refresh_room_state(room_id, "queue_updated")


async def _vote_queue_entry(room_id: str, queue_entry_id: str, user_id: str, vote_type: str) -> dict:
    if vote_type not in {"upvote", "downvote", "neutral"}:
        raise HTTPException(status_code=400, detail="Invalid vote type")

    session_factory = _get_session_factory()
    async with session_factory() as session:
        queue_entry = await session.get(QueueEntry, queue_entry_id)
        if not queue_entry or queue_entry.roomId != room_id:
            raise HTTPException(status_code=404, detail="Queue entry not found")

        existing = (
            await session.execute(
                select(SongFeedback).where(
                    SongFeedback.queueEntryId == queue_entry_id, SongFeedback.userId == user_id
                )
            )
        ).scalar_one_or_none()

        if vote_type == "neutral":
            if existing:
                session.delete(existing)
        else:
            mapped_feedback = _ui_to_feedback(vote_type)
            if mapped_feedback is None:
                raise HTTPException(status_code=400, detail="Invalid vote type")

            if existing:
                existing.type = mapped_feedback
                existing.votedAt = datetime.now(UTC).replace(tzinfo=None)
            else:
                session.add(
                    SongFeedback(
                        queueEntryId=queue_entry_id,
                        userId=user_id,
                        type=mapped_feedback,
                    )
                )

        feedback_rows = (
            await session.execute(
                select(SongFeedback).where(SongFeedback.queueEntryId == queue_entry_id)
            )
        ).scalars()
        upvotes = sum(1 for feedback in feedback_rows if feedback.type == FeedbackType.LIKE)

        feedback_rows = (
            await session.execute(
                select(SongFeedback).where(SongFeedback.queueEntryId == queue_entry_id)
            )
        ).scalars()
        downvotes = sum(1 for feedback in feedback_rows if feedback.type == FeedbackType.DISLIKE)
        queue_entry.voteScore = upvotes - downvotes
        queue_entry.orderRank = float(queue_entry.position) - float(queue_entry.voteScore) / 100.0
        await session.commit()

    return await refresh_room_state(room_id, "vote_updated")


async def _set_playback_state(room_id: str, user_id: str, action: str) -> dict:
    if action not in {"pause", "resume", "stop"}:
        raise HTTPException(status_code=400, detail="Invalid playback action")

    session_factory = _get_session_factory()
    async with session_factory() as session:
        room = await session.get(DbRoom, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if room.hostedBy != user_id:
            raise HTTPException(status_code=403, detail="Only the host can control playback")

        playback_session = (
            await session.execute(
                select(PlaybackSession)
                .where(PlaybackSession.roomId == room_id)
                .order_by(PlaybackSession.startedAt.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not playback_session:
            current_queue_entry = (
                await session.execute(
                    select(QueueEntry)
                    .where(QueueEntry.roomId == room_id)
                    .order_by(QueueEntry.position.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not current_queue_entry:
                raise HTTPException(status_code=400, detail="No queued songs")

            current_queue_entry.status = QueueEntryStatus.PLAYING
            playback_session = PlaybackSession(
                playbackSessionId=str(uuid.uuid4()),
                roomId=room_id,
                queueEntryId=current_queue_entry.queueEntryId,
                state=PlaybackState.PLAYING,
                elapsedTime=0,
            )
            session.add(playback_session)

        if action == "pause":
            playback_session.state = PlaybackState.PAUSED
            playback_session.pausedAt = datetime.now(UTC).replace(tzinfo=None)
        elif action == "stop":
            playback_session.state = PlaybackState.STOPPED
            playback_session.pausedAt = datetime.now(UTC).replace(tzinfo=None)
        else:
            playback_session.state = PlaybackState.PLAYING
            playback_session.pausedAt = None

        await session.commit()

    return await refresh_room_state(room_id, "playback_updated")


async def _leave_room(room_id: str, user_id: str) -> dict:
    await db_leave_room(user_id, room_id)
    return await refresh_room_state(room_id, "participant_left")


async def _delete_room(room_id: str, user_id: str) -> dict:
    session_factory = _get_session_factory()
    async with session_factory() as session:
        room = await session.get(DbRoom, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        if room.hostedBy != user_id:
            raise HTTPException(status_code=403, detail="Only host can delete room")

        room.status = RoomStatus.DELETED
        memberships = (
            await session.execute(
                select(RoomMembership).where(RoomMembership.roomId == room_id)
            )
        ).scalars()
        for membership in memberships:
            membership.membershipStatus = MembershipStatus.INACTIVE
            if membership.leftAt is None:
                membership.leftAt = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()

    return await refresh_room_state(room_id, "room_deleted")


async def send_room_state(room_id: str) -> None:
    if room_id not in room_state_cache:
        try:
            await refresh_room_state(room_id)
        except HTTPException:
            return

    room_state = room_state_cache.get(room_id, {})
    if room_id in active_room_connections:
        for websocket in list(active_room_connections[room_id]):
            try:
                await websocket.send_text(json.dumps(room_state))
            except Exception as e:
                print(f"Error sending to websocket: {e}")
                active_room_connections[room_id].discard(websocket)


async def handle_room_events(room_id: str, data: str) -> None:
    try:
        event = json.loads(data)
    except json.JSONDecodeError:
        print(f"Invalid JSON received: {data}")
        return

    event_type = event.get("type")
    try:
        if event_type == "addqueue":
            await _add_to_queue(room_id, event.get("track"), event.get("user_id"))
        elif event_type == "vote":
            await _vote_queue_entry(
                room_id=room_id,
                queue_entry_id=event.get("queue_entry_id"),
                user_id=event.get("user_id"),
                vote_type=event.get("vote_type", "neutral"),
            )
        elif event_type == "playback":
            await _set_playback_state(
                room_id=room_id,
                user_id=event.get("user_id"),
                action=event.get("action"),
            )
        elif event_type == "leave":
            await _leave_room(room_id, event.get("user_id"))
    except HTTPException:
        pass


async def _get_spotify_access_token() -> str:
    cached_token = spotify_token_cache.get("token")
    cached_expiry = spotify_token_cache.get("expires_at")
    if isinstance(cached_token, str) and isinstance(cached_expiry, datetime):
        if datetime.now(UTC) < cached_expiry:
            return cached_token

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Spotify credentials are not configured on the backend",
        )

    auth_value = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth_value}"},
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise HTTPException(status_code=502, detail="Spotify token response invalid")
        spotify_token_cache["token"] = token
        spotify_token_cache["expires_at"] = datetime.now(UTC).replace(
            microsecond=0
        ) + timedelta(seconds=max(60, expires_in - 60))
        return token


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/hello")
async def root():
    return {"message": "Hello World"}


@app.get("/db-health")
async def db_health():
    result = await db_check_db_health()
    return {"db-status": result.get("status"), **result}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    active_room_connections[room_id].add(websocket)
    await send_room_state(room_id)

    try:
        while True:
            data = await websocket.receive_text()
            await handle_room_events(room_id, data)
            await send_room_state(room_id)
    finally:
        active_room_connections[room_id].discard(websocket)


@app.post("/auth/account", response_model=AuthResponse)
async def auth_account(auth_data: AuthRequest):
    return {
        "success": True,
        "message": "Account authentication successful",
        "token": "dummy_account_token_12345",
    }


@app.post("/create_room", response_model=RoomResponse)
async def create_room_endpoint(room_data: CreateRoomRequest):
    user = await db_get_user(room_data.user_id)
    if not user:
        try:
            await db_create_user(room_data.user_id, room_data.user_id)
            user = await db_get_user(room_data.user_id)
        except ValueError:
            user = await db_get_user(room_data.user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

    if not user:
        raise HTTPException(status_code=500, detail="Failed to create or retrieve user")

    await ensure_provider_exists(room_data.supported_provider_id)

    try:
        room = await db_create_room(
            room_data.name,
            room_data.user_id,
            room_data.supported_provider_id,
        )
        await ensure_active_membership(room_data.user_id, room.roomId)
        await refresh_room_state(room.roomId, "room_created")
        return {
            "success": True,
            "message": f"Successfully created room {room.roomId}",
            "room_id": room.roomId,
            "join_code": room.joinCode,
        }
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=400, detail="Room already exists")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")


@app.post("/join_room", response_model=RoomResponse)
async def join_room(room_data: RoomRequest):
    user = await db_get_user(room_data.user_id)
    if not user:
        try:
            await db_create_user(room_data.user_id, room_data.user_id)
        except ValueError as e:
            if "already exists" not in str(e):
                raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

    room = await db_get_room_by_join_code(room_data.room_id.upper())
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")

    try:
        await ensure_active_membership(room_data.user_id, room.roomId)
        await refresh_room_state(room.roomId, "participant_joined")
        await send_room_state(room.roomId)
        return {
            "success": True,
            "message": f"Successfully joined room {room.roomId}",
            "room_id": room.roomId,
            "join_code": room.joinCode,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join room: {str(e)}")


@app.post("/leave_room", response_model=RoomResponse)
async def leave_room(room_data: RoomRequest):
    user = await db_get_user(room_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    room = await db_get_room(room_data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    try:
        await _leave_room(room_data.room_id, room_data.user_id)
        await send_room_state(room_data.room_id)
        return {
            "success": True,
            "message": f"Successfully left room {room_data.room_id}",
            "room_id": room_data.room_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to leave room: {str(e)}")


@app.post("/delete_room", response_model=RoomResponse)
async def delete_room(room_data: DeleteRoomRequest):
    await _delete_room(room_data.room_id, room_data.user_id)
    await send_room_state(room_data.room_id)
    return {
        "success": True,
        "message": f"Successfully deleted room {room_data.room_id}",
        "room_id": room_data.room_id,
    }


@app.get("/rooms/{room_id}/state")
async def get_room_state(room_id: str):
    room_state = await refresh_room_state(room_id)
    return room_state


@app.get("/rooms/{room_id}/search")
async def search_tracks(room_id: str, q: str = Query(..., min_length=1, max_length=120)):
    room = await db_get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")
    if str(room.supportedProviderId).lower() != "spotify":
        raise HTTPException(status_code=400, detail="Only spotify is supported in MVP")

    token = await _get_spotify_access_token()
    spotify_market = os.getenv("SPOTIFY_MARKET", "CH")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://api.spotify.com/v1/search",
            # Spotify search currently enforces max limit=10.
            params={"q": q, "type": "track", "limit": 10, "market": spotify_market},
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"Spotify search failed: {detail}",
            ) from exc
        payload = response.json()

    items = payload.get("tracks", {}).get("items", [])
    tracks = []
    for item in items:
        album = item.get("album") or {}
        images = album.get("images") or []
        artists = item.get("artists") or []
        tracks.append(
            {
                "trackId": item.get("id"),
                "providerTrackId": item.get("id"),
                "title": item.get("name") or "Unknown title",
                "artist": ", ".join(artist.get("name", "") for artist in artists if artist.get("name")) or "Unknown artist",
                "album": album.get("name") or "",
                "duration": int((item.get("duration_ms") or 0) / 1000),
                "coverUrl": images[0].get("url") if images else "",
                "deepLink": item.get("external_urls", {}).get("spotify", ""),
            }
        )

    return {"provider": "spotify", "query": q, "tracks": tracks}


@app.post("/rooms/{room_id}/queue/{queue_entry_id}/vote")
async def vote_queue_entry(room_id: str, queue_entry_id: str, vote_data: VoteRequest):
    room_state = await _vote_queue_entry(
        room_id=room_id,
        queue_entry_id=queue_entry_id,
        user_id=vote_data.user_id,
        vote_type=vote_data.vote_type,
    )
    await send_room_state(room_id)
    return {"success": True, "room": room_state}


@app.post("/rooms/{room_id}/playback")
async def control_playback(room_id: str, playback_data: PlaybackRequest):
    room_state = await _set_playback_state(
        room_id=room_id,
        user_id=playback_data.user_id,
        action=playback_data.action,
    )
    await send_room_state(room_id)
    return {"success": True, "room": room_state}


@app.post("/add_music_provider", response_model=AddMusicProviderResponse)
async def add_music_provider(provider_data: AddMusicProviderRequest):
    user = await db_get_user(provider_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        provider_account = await db_create_provider_account(
            provider_data.user_id,
            provider_data.provider_id,
            provider_data.external_user_id,
        )
        return {
            "success": True,
            "message": f"Successfully linked provider {provider_data.provider_id} to user",
            "provider_account_id": provider_account.providerAccountId,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add music provider: {str(e)}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    generic_connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
            await websocket.send_text("No detail provided")
    finally:
        generic_connections.discard(websocket)


@app.post("/rooms/{room_id}/queue")
async def add_queue_entry(room_id: str, event: dict):
    track_data = event.get("track")
    user_id = event.get("user_id")
    room_state = await _add_to_queue(room_id, track_data, user_id)
    await send_room_state(room_id)
    return {"success": True, "room": room_state}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
