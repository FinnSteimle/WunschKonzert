import {
	type AppleMusicLinkRequest,
	type AppleMusicProfileDto,
	type CreateRoomRequest,
	type DeleteRoomRequest,
	type LeaveRoomRequest,
	type RoomAvailabilityRequest,
	type RoomAvailabilityResponse,
	type RoomRequest,
	type RoomResponse,
	type RoomStateDto,
	type SearchResponseDto
} from '$lib/types/api';

/**
 * Base URL for REST calls. Order:
 * 1. PUBLIC_API_URL when set: local dev (`http://localhost:8000`) and CI-built images with an explicit API host.
 * 2. In the browser on localhost frontends (ports 3000 / 5173 / 4173), call the API directly on port 8000; there is no
 *    `/api` reverse proxy like in production Caddy, so same-origin `/api` would 404.
 * 3. Otherwise same-origin `/api` (matches Caddy `https://host/api` → backend) and avoids mixed-content on HTTPS.
 * 4. SSR / tests: localhost default (tests should set PUBLIC_API_URL via `.env` or Vitest env).
 */
export function getApiBaseUrl(): string {
	const fromEnv = import.meta.env.PUBLIC_API_URL;
	if (typeof fromEnv === 'string' && fromEnv.trim() !== '') {
		return fromEnv.trim().replace(/\/$/, '');
	}
	if (typeof window !== 'undefined' && window.location?.origin) {
		if (shouldUseDirectLocalApiFromBrowser()) {
			return 'http://127.0.0.1:8000';
		}
		return `${window.location.origin}/api`;
	}
	return 'http://localhost:8000';
}

/** WebSocket origin; mirrors `getApiBaseUrl` (env → direct local port 8000 → same-origin /api with correct ws/wss). */
export function getWsBaseUrl(): string {
	const fromEnv = import.meta.env.PUBLIC_WS_URL;
	if (typeof fromEnv === 'string' && fromEnv.trim() !== '') {
		return fromEnv.trim().replace(/\/$/, '');
	}
	if (typeof window !== 'undefined' && window.location?.host) {
		if (shouldUseDirectLocalApiFromBrowser()) {
			return 'ws://127.0.0.1:8000';
		}
		const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
		return `${scheme}://${window.location.host}/api`;
	}
	return 'ws://localhost:8000';
}

/** True when the UI is served on common local frontend ports without a same-host `/api` proxy. */
function shouldUseDirectLocalApiFromBrowser(): boolean {
	if (typeof window === 'undefined' || !window.location?.hostname) return false;
	const { hostname, port } = window.location;
	const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === 'frontend';
	if (!isLocal) return false;
	return port === '3000' || port === '5173' || port === '4173';
}

const PROVIDER_ERROR_MESSAGES: Record<string, string> = {
	subscription_error: 'An active Apple Music subscription is required.',
	invalid_music_user_token: 'Apple Music authorization failed. Please try linking again.',
	invalid_request: 'Apple Music link request was invalid.',
	apple_music_not_configured: 'Apple Music is not configured on this server.',
	not_linked: 'Apple Music account is not linked.',
	needs_relink: 'Your music account link expired. Please link again.'
};

export class ApiRequestError extends Error {
	readonly status: number;
	readonly code?: string;

	constructor(message: string, status: number, code?: string) {
		super(message);
		this.name = 'ApiRequestError';
		this.status = status;
		this.code = code;
	}

	get needsRelink(): boolean {
		return this.code === 'needs_relink';
	}
}

export function isNeedsRelinkError(err: unknown): err is ApiRequestError {
	return err instanceof ApiRequestError && err.needsRelink;
}

function formatApiErrorMessage(status: number, payload: unknown): string {
	if (payload && typeof payload === 'object') {
		const record = payload as Record<string, unknown>;
		const detail = record.detail;
		if (detail && typeof detail === 'object' && detail !== null && 'code' in detail) {
			const code = String((detail as { code: unknown }).code);
			if (code in PROVIDER_ERROR_MESSAGES) {
				return PROVIDER_ERROR_MESSAGES[code];
			}
			return code;
		}
		if (typeof detail === 'string' && detail.trim()) {
			return detail;
		}
		if (typeof record.message === 'string' && record.message.trim()) {
			return record.message;
		}
	}
	return `Request failed: ${status}`;
}

function extractErrorCode(payload: unknown): string | undefined {
	if (!payload || typeof payload !== 'object') return undefined;
	const detail = (payload as Record<string, unknown>).detail;
	if (detail && typeof detail === 'object' && detail !== null && 'code' in detail) {
		return String((detail as { code: unknown }).code);
	}
	return undefined;
}

async function parseResponse<T>(response: Response): Promise<T> {
	if (!response.ok) {
		let message = `Request failed: ${response.status}`;
		let code: string | undefined;
		try {
			const payload = await response.json();
			code = extractErrorCode(payload);
			message = formatApiErrorMessage(response.status, payload);
		} catch {
			// Ignore parse failures and keep the fallback message.
		}
		throw new ApiRequestError(message, response.status, code);
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
		const response = await fetch(`${getApiBaseUrl()}/rooms/${encodeURIComponent(roomId)}/state`);
		return parseResponse<RoomStateDto>(response);
	},

	async searchSongs(roomId: string, query: string): Promise<SearchResponseDto> {
		const response = await fetch(
			`${getApiBaseUrl()}/rooms/${encodeURIComponent(roomId)}/search?q=${encodeURIComponent(query)}`
		);
		return parseResponse<SearchResponseDto>(response);
	},

	async getSpotifyLoginUrl(
		userId: string,
		displayName: string,
		returnTo: string,
		options?: { forceConsent?: boolean }
	): Promise<{ auth_url: string }> {
		const params = new URLSearchParams({
			user_id: userId,
			display_name: displayName,
			return_to: returnTo
		});
		if (options?.forceConsent) {
			params.set('force_consent', 'true');
		}
		const response = await fetch(`${getApiBaseUrl()}/auth/spotify/login?${params}`);
		return parseResponse<{ auth_url: string }>(response);
	},

	async getSpotifyToken(userId: string): Promise<{ access_token: string }> {
		const params = new URLSearchParams({ user_id: userId });
		const response = await fetch(`${getApiBaseUrl()}/auth/spotify/token?${params}`);
		return parseResponse<{ access_token: string }>(response);
	},

	async getAppleMusicDeveloperToken(userId: string): Promise<{ developer_token: string }> {
		const params = new URLSearchParams({ user_id: userId });
		const response = await fetch(
			`${getApiBaseUrl()}/auth/apple-music/developer-token?${params}`
		);
		return parseResponse<{ developer_token: string }>(response);
	},

	async linkAppleMusic(
		body: AppleMusicLinkRequest
	): Promise<{ storefront: string; display_name: string | null }> {
		return postJson<{ storefront: string; display_name: string | null }>(
			'/auth/apple-music/link',
			body
		);
	},

	async getAppleMusicToken(userId: string): Promise<{ music_user_token: string }> {
		const params = new URLSearchParams({ user_id: userId });
		const response = await fetch(`${getApiBaseUrl()}/auth/apple-music/token?${params}`);
		return parseResponse<{ music_user_token: string }>(response);
	},

	async getAppleMusicProfile(userId: string): Promise<AppleMusicProfileDto> {
		const params = new URLSearchParams({ user_id: userId });
		const response = await fetch(`${getApiBaseUrl()}/auth/apple-music/profile?${params}`);
		return parseResponse<AppleMusicProfileDto>(response);
	}
};
