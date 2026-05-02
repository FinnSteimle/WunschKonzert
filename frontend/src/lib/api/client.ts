import {
	type CreateRoomRequest,
	type DeleteRoomRequest,
	type LeaveRoomRequest,
	type RoomAvailabilityRequest,
	type RoomAvailabilityResponse,
	type RoomRequest,
	type RoomResponse,
	type RoomStateDto,
	type SearchResponseDto,
	type TrackDto,
} from '$lib/types/api';

/**
 * Base URL for REST calls. Order:
 * 1. PUBLIC_API_URL when set — local dev (`http://localhost:8000`) and CI-built images with an explicit API host.
 * 2. In the browser, same-origin `/api` — matches Caddy (`https://host/api` → backend) and avoids mixed-content on HTTPS.
 * 3. SSR / tests: localhost default (tests should set PUBLIC_API_URL via `.env` or Vitest env).
 */
export function getApiBaseUrl(): string {
	const fromEnv = import.meta.env.PUBLIC_API_URL;
	if (typeof fromEnv === 'string' && fromEnv.trim() !== '') {
		return fromEnv.trim().replace(/\/$/, '');
	}
	if (typeof window !== 'undefined' && window.location?.origin) {
		return `${window.location.origin}/api`;
	}
	return 'http://localhost:8000';
}

/** WebSocket origin; mirrors `getApiBaseUrl` (env → same-origin /api with correct ws/wss). */
export function getWsBaseUrl(): string {
	const fromEnv = import.meta.env.PUBLIC_WS_URL;
	if (typeof fromEnv === 'string' && fromEnv.trim() !== '') {
		return fromEnv.trim().replace(/\/$/, '');
	}
	if (typeof window !== 'undefined' && window.location?.host) {
		const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
		return `${scheme}://${window.location.host}/api`;
	}
	return 'ws://localhost:8000';
}

async function parseResponse<T>(response: Response): Promise<T> {
	if (!response.ok) {
		let message = `Request failed: ${response.status}`;
		try {
			const payload = await response.json();
			message = payload?.detail ?? payload?.message ?? message;
		} catch {
			// Ignore parse failures and keep the fallback message.
		}
		throw new Error(message);
	}
	return (await response.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
	const response = await fetch(`${getApiBaseUrl()}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	return parseResponse<T>(response);
}

export const apiClient = {
	async createRoom(payload: CreateRoomRequest): Promise<RoomResponse> {
		return postJson<RoomResponse>('/create_room', payload);
	},

	async joinRoom(payload: RoomRequest): Promise<RoomResponse> {
		return postJson<RoomResponse>('/join_room', payload);
	},

	async leaveRoom(payload: LeaveRoomRequest): Promise<RoomResponse> {
		return postJson<RoomResponse>('/leave_room', payload);
	},

	async deleteRoom(payload: DeleteRoomRequest): Promise<RoomResponse> {
		return postJson<RoomResponse>('/delete_room', payload);
	},

	async getRoomsAvailability(payload: RoomAvailabilityRequest): Promise<RoomAvailabilityResponse> {
		return postJson<RoomAvailabilityResponse>('/rooms/availability', payload);
	},

	async getRoomState(roomId: string): Promise<RoomStateDto> {
		const response = await fetch(
			`${getApiBaseUrl()}/rooms/${encodeURIComponent(roomId)}/state`
		);
		return parseResponse<RoomStateDto>(response);
	},

	async searchSongs(roomId: string, query: string): Promise<SearchResponseDto> {
		const response = await fetch(
			`${getApiBaseUrl()}/rooms/${encodeURIComponent(roomId)}/search?q=${encodeURIComponent(query)}`
		);
		return parseResponse<SearchResponseDto>(response);
	},

	async addQueueEntry(roomId: string, userId: string, track: TrackDto): Promise<{ success: boolean }> {
		return postJson<{ success: boolean }>(`/rooms/${encodeURIComponent(roomId)}/queue`, {
			type: 'addqueue',
			user_id: userId,
			track
		});
	},

	async getSpotifyLoginUrl(
		userId: string,
		returnTo: string
	): Promise<{ auth_url: string }> {
		const params = new URLSearchParams({ user_id: userId, return_to: returnTo });
		const response = await fetch(`${getApiBaseUrl()}/auth/spotify/login?${params}`);
		return parseResponse<{ auth_url: string }>(response);
	},

	async getSpotifyToken(userId: string): Promise<{ access_token: string }> {
		const params = new URLSearchParams({ user_id: userId });
		const response = await fetch(`${getApiBaseUrl()}/auth/spotify/token?${params}`);
		return parseResponse<{ access_token: string }>(response);
	}
};
