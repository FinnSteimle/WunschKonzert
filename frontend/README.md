# WunschKonzert frontend

SvelteKit 2 + Svelte 5 app for collaborative music rooms (Spotify / Apple Music). Real-time state over WebSockets; queue actions use the socket, not REST.

## Prerequisites

- Node.js 22+
- Backend API on port 8000 (see repo root `README.md` or `make run`)

## Setup

```bash
cd frontend
cp .env.example .env
npm ci
```

### Environment variables

| Variable | Purpose |
|----------|---------|
| `PUBLIC_API_URL` | REST base URL (default in `.env.example`: `http://localhost:8000`) |
| `PUBLIC_WS_URL` | WebSocket base URL (default: `ws://localhost:8000`) |

In production (Docker/Caddy), these are baked in at build time. Locally, when Vite serves on port 5173, the client auto-targets `http://127.0.0.1:8000` if env vars are unset.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Vite dev server (http://localhost:5173) |
| `npm run build` | Production build (`adapter-node` when `DOCKER_BUILD=true`) |
| `npm run preview` | Preview production build |
| `npm run check` | `svelte-check` (types) |
| `npm run lint` | ESLint |
| `npm test` | Vitest unit tests |
| `npm run format` | Prettier |

## Routes

| Path | Description |
|------|-------------|
| `/` | Landing, join by code, recent rooms |
| `/create` | Create room (Spotify / Apple Music) |
| `/join/{code}` | Redirects to `/room/{code}` |
| `/room/{code}` | Room UI; URL uses 6-character **join code** only |

## Architecture (high level)

```text
src/routes/          SvelteKit pages
src/lib/api/         REST client (client.ts)
src/lib/realtime/    RoomSocketClient (WebSocket)
src/lib/stores/      roomStore (room snapshot + connection)
src/lib/room/        slug parsing, joinRoomByCode helper
src/lib/session/     Anonymous user id (localStorage)
src/lib/playback/    Spotify / Apple Music host players
src/lib/components/  Feature UI + shadcn/ui primitives
```

Room page orchestration is split across:

- `useRoomPage.svelte.ts`: handlers, mount, link-join UI
- `useRoomSession.svelte.ts`: WebSocket session lifecycle
- `useRoomEffects.svelte.ts`: toasts, recent rooms, activity log sync
- `useRoomSpotifyOAuth.svelte.ts`: Spotify OAuth return query handling
- `useHostPlayback.svelte.ts`: host playback sync

## Security model (browser)

- Each browser gets a random `user_id` in `localStorage` (`wk_user_id`).
- That id is sent on REST and WebSocket messages; **the backend must authorize actions** (membership, host role), not trust the id alone.
- OAuth tokens are fetched from the API by `user_id`; treat this as a demo trust boundary and document it in your thesis.

## Docker

```bash
docker build -t wunschkonzert-frontend --target runner \
  --build-arg PUBLIC_API_URL=https://your-host/api \
  --build-arg PUBLIC_WS_URL=wss://your-host/api \
  frontend/
```

Runtime image listens on port 3000.

## Testing

```bash
npm test
```

Coverage thresholds (80% lines/statements) exclude `components/ui`, `playback`, and `types`; see `vite.config.ts`.
