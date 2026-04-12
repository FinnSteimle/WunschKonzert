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

const API_BASE_URL = import.meta.env.PUBLIC_API_URL ?? 'http://localhost:8000';

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
	const response = await fetch(`${API_BASE_URL}${path}`, {
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
		const response = await fetch(`${API_BASE_URL}/rooms/${encodeURIComponent(roomId)}/state`);
		return parseResponse<RoomStateDto>(response);
	},

	async searchSongs(roomId: string, query: string): Promise<SearchResponseDto> {
		const response = await fetch(
			`${API_BASE_URL}/rooms/${encodeURIComponent(roomId)}/search?q=${encodeURIComponent(query)}`
		);
		return parseResponse<SearchResponseDto>(response);
	},

	async addQueueEntry(roomId: string, userId: string, track: TrackDto): Promise<{ success: boolean }> {
		return postJson<{ success: boolean }>(`/rooms/${encodeURIComponent(roomId)}/queue`, {
			type: 'addqueue',
			user_id: userId,
			track
		});
	}
};

export { API_BASE_URL };
