#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Use CHECK_HOST if provided (e.g., in CI dind), otherwise default to localhost
HOST="${CHECK_HOST:-localhost}"

echo "--- Testing Independent Backend ---"
docker compose -f backend/compose.yaml up -d --build

# Wait for backend health
MAX_RETRIES=30
COUNT=0
echo "Waiting for backend health at http://${HOST}:8000/health..."
# Use GET instead of HEAD because FastAPI returns 405 for HEAD on GET-only routes
until curl --output /dev/null --silent --fail "http://${HOST}:8000/health"; do
    printf '.'
    sleep 2
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo -e "\n${RED}Backend failed to start independently${NC}"
        docker compose -f backend/compose.yaml logs
        docker compose -f backend/compose.yaml down -v
        exit 1
    fi
done

echo -e "\n${GREEN}Backend is running independently!${NC}"
docker compose -f backend/compose.yaml down -v

echo "--- Testing Independent Frontend ---"
docker compose -f frontend/compose.yaml up -d --build

# Wait for frontend responsiveness
COUNT=0
echo "Waiting for frontend responsiveness at http://${HOST}:3000..."
until curl --output /dev/null --silent --fail "http://${HOST}:3000"; do
    printf '.'
    sleep 2
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo -e "\n${RED}Frontend failed to start independently${NC}"
        docker compose -f frontend/compose.yaml logs
        docker compose -f frontend/compose.yaml down -v
        exit 1
    fi
done

echo -e "\n${GREEN}Frontend is running independently!${NC}"
docker compose -f frontend/compose.yaml down -v

echo -e "\n${GREEN}All components can run independently.${NC}"
