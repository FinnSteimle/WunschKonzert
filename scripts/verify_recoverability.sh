#!/bin/bash
# NFR Verification Tool: WUN-90 Recoverability (Deep State Persistence)
# Verifies that songs and votes survive a hard crash.

set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
HEALTH_URL="$BACKEND_URL/health"
MAX_WAIT=120

log() { echo -e "\033[0m[$(date +%T)] $1"; }
success() { echo -e "\033[0;32m[SUCCESS] $1\033[0m"; }
error() { echo -e "\033[0;31m[ERROR] $1\033[0m"; }

# Setup Room
log "Creating test room..."
curl -s -X POST "$BACKEND_URL/debug/seed_user" -H "Content-Type: application/json" -d '{"user_id": "nfr-user", "display_name": "NFR-Bot"}' > /dev/null
CREATE_RES=$(curl -s -X POST "$BACKEND_URL/create_room" -H "Content-Type: application/json" -d '{"name": "Persistence Test", "user_id": "nfr-user", "display_name": "NFR-Bot", "supported_provider_id": "spotify"}')
ROOM_ID=$(echo $CREATE_RES | python3 -c "import sys, json; print(json.load(sys.stdin).get('room_id', ''))")
JOIN_CODE=$(echo $CREATE_RES | python3 -c "import sys, json; print(json.load(sys.stdin).get('join_code', ''))")

if [ -z "$ROOM_ID" ]; then error "Failed to create room"; exit 1; fi
success "Room created: $JOIN_CODE ($ROOM_ID)"

# Add Song and Vote via Service Layer (Docker Exec)
log "Adding song and upvote via service layer..."
docker exec $(docker compose ps -q api) uv run python -c "
import asyncio
import services.room_service as rs
from models.domain import FeedbackType

async def setup():
    # Add a song
    track = {
        'trackId': 'test-track-123',
        'providerTrackId': 'spotify:track:123',
        'title': 'Persistence Anthem',
        'artist': 'The Survivors',
        'album': 'NFR Vol 1',
        'duration': 200,
        'coverUrl': '',
        'deepLink': ''
    }
    state = await rs.add_to_queue('$ROOM_ID', track, 'nfr-user')
    entry_id = state['queue'][0]['queueEntryId']
    
    # Add an upvote
    await rs.vote_queue_entry('$ROOM_ID', entry_id, 'nfr-user', 'upvote')
    print(entry_id)

asyncio.run(setup())
" > /tmp/nfr_entry_id

ENTRY_ID=$(cat /tmp/nfr_entry_id | tail -n 1)
success "Added song (ID: $ENTRY_ID) with 1 upvote."

# Crash Simulation
log "Crashing services (internal kill)..."
API_CONTAINER=$(docker compose ps -q api)
DB_CONTAINER=$(docker compose ps -q db)

docker exec "$API_CONTAINER" sh -c "kill -9 1" || echo "API process killed"
docker exec "$DB_CONTAINER" sh -c "kill -9 1" || echo "DB process killed"

log "Waiting for recovery..."
sleep 5
until curl -s "$HEALTH_URL" | grep -q '"status":"ok"'; do printf "."; sleep 1; done
echo ""
success "System recovered."

# Verify Deep State
log "Verifying deep state persistence..."
docker exec $(docker compose ps -q api) uv run python -c "
import asyncio
import services.room_service as rs

async def verify():
    state = await rs.refresh_room_state('$ROOM_ID')
    queue = state.get('queue', [])
    if not queue:
        print('FAIL: Queue empty')
        return
    
    entry = queue[0]
    score = entry.get('voteScore', 0)
    title = entry.get('track', {}).get('title', '')
    
    if title == 'Persistence Anthem' and score == 1:
        print('PASS')
    else:
        print(f'FAIL: Title={title}, Score={score}')

asyncio.run(verify())
" > /tmp/nfr_result

RESULT=$(cat /tmp/nfr_result | tail -n 1)

if [ "$RESULT" == "PASS" ]; then
    success "DEEP PERSISTENCE VERIFIED: Songs and votes survived the crash."
else
    error "PERSISTENCE FAILED: $RESULT"
    exit 1
fi
