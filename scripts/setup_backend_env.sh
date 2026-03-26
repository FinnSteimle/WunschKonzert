#!/bin/bash
# Script to set up backend environment variables for CI/CD
# Copies .env.example to .env and replaces placeholders with CI variables

set -e

# Change to backend directory
cd backend || { echo "Error: Could not change to backend directory"; exit 1; }

# Copy .env.example to .env
echo "Copying .env.example to .env..."
cp .env.example .env

# Replace environment variables with CI variables (with fallbacks)
echo "Setting up environment variables..."
sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-changeme}/" .env
sed -i "s/POSTGRES_DB=.*/POSTGRES_DB=${POSTGRES_DB:-wunschkonzert}/" .env
sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD:-changeme}@db:5432/${POSTGRES_DB:-wunschkonzert}|" .env
sed -i "s/ENVIRONMENT=.*/ENVIRONMENT=production/" .env
sed -i "s/SPOTIFY_CLIENT_ID=.*/SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID:-your_spotify_client_id}/" .env
sed -i "s/SPOTIFY_CLIENT_SECRET=.*/SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET:-your_spotify_client_secret}/" .env

echo "Backend environment setup complete."
cd ..
