import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';

function mockJsonResponse<T>(ok: boolean, jsonValue: T, status = 200): Response {
	return {
		ok,
		status,
		json: async () => jsonValue
	} as Response;
}

describe('apiClient', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it('posts create room payload and returns parsed response', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			mockJsonResponse(true, {
				success: true,
				message: 'ok',
				room_id: 'room-1',
				join_code: 'AB2CD3'
			})
		);
		vi.stubGlobal('fetch', fetchMock);

		const payload = {
			name: 'My Room',
			user_id: 'U_123',
			display_name: 'Alice',
			supported_provider_id: 'spotify' as const
		};
		const result = await apiClient.createRoom(payload);

		expect(result).toEqual({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'AB2CD3'
		});
		expect(fetchMock).toHaveBeenCalledOnce();
		expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/create_room', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});
	});

	it('uses backend error detail/message when present', async () => {
		const fetchMock = vi
			.fn()
			.mockResolvedValueOnce({
				ok: false,
				status: 400,
				json: async () => ({ detail: 'Invalid room name' })
			})
			.mockResolvedValueOnce({
				ok: false,
				status: 409,
				json: async () => ({ message: 'Duplicate room' })
			});
		vi.stubGlobal('fetch', fetchMock);

		await expect(
			apiClient.createRoom({
				name: 'Friday vibes',
				user_id: 'U_TESTUSER1',
				display_name: 'Alice',
				supported_provider_id: 'spotify'
			})
		).rejects.toThrow('Invalid room name');

		await expect(
			apiClient.createRoom({
				name: 'Friday vibes',
				user_id: 'U_TESTUSER1',
				display_name: 'Alice',
				supported_provider_id: 'spotify'
			})
		).rejects.toThrow('Duplicate room');
	});

	it('throws backend detail message for failed join requests', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			mockJsonResponse(false, { detail: 'Room already exists' }, 409)
		);
		vi.stubGlobal('fetch', fetchMock);

		await expect(
			apiClient.joinRoom({ join_code: 'AB2CD3', user_id: 'U_123', display_name: 'Alice' })
		).rejects.toThrow('Room already exists');
	});

	it('posts join room payload and returns parsed response', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			mockJsonResponse(true, {
				success: true,
				message: 'joined',
				room_id: 'room-1',
				join_code: 'AB2CD3'
			})
		);
		vi.stubGlobal('fetch', fetchMock);

		const payload = {
			join_code: 'AB2CD3',
			user_id: 'U_123',
			display_name: 'Alice'
		};

		const result = await apiClient.joinRoom(payload);

		expect(result).toEqual({
			success: true,
			message: 'joined',
			room_id: 'room-1',
			join_code: 'AB2CD3'
		});
		expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/join_room', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});
	});

	it('posts delete room payload and returns parsed response', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			mockJsonResponse(true, {
				success: true,
				message: 'deleted',
				room_id: 'room-1',
				join_code: null
			})
		);
		vi.stubGlobal('fetch', fetchMock);

		const payload = {
			room_id: 'room-1',
			user_id: 'U_123'
		};

		const result = await apiClient.deleteRoom(payload);

		expect(result).toEqual({
			success: true,
			message: 'deleted',
			room_id: 'room-1',
			join_code: null
		});
		expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/delete_room', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});
	});

	it('falls back to status text when error body cannot be parsed', async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: false,
			status: 503,
			json: async () => {
				throw new Error('not json');
			}
		});
		vi.stubGlobal('fetch', fetchMock);

		await expect(
			apiClient.leaveRoom({ room_id: 'room-1', user_id: 'U_123' })
		).rejects.toThrow('Request failed: 503');
	});

	it('encodes room id when requesting room state', async () => {
		const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse(true, { status: 'ok' }));
		vi.stubGlobal('fetch', fetchMock);

		await apiClient.getRoomState('room/with space');

		expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/rooms/room%2Fwith%20space/state');
	});

	it('encodes room id and query when searching songs', async () => {
		const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse(true, { tracks: [] }));
		vi.stubGlobal('fetch', fetchMock);

		await apiClient.searchSongs('room/1', 'AC/DC hits');

		expect(fetchMock).toHaveBeenCalledWith(
			'http://localhost:8000/rooms/room%2F1/search?q=AC%2FDC%20hits'
		);
	});

	it('sends queue entry with expected JSON shape', async () => {
		const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse(true, { success: true }));
		vi.stubGlobal('fetch', fetchMock);

		const track = {
			trackId: 't1',
			providerTrackId: 'spotify:t1',
			title: 'Song',
			artist: 'Artist',
			album: 'Album',
			duration: 100,
			coverUrl: 'https://example.com/cover.jpg',
			deepLink: 'https://example.com/track/t1'
		};
		await apiClient.addQueueEntry('room-1', 'U_123', track);

		expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/rooms/room-1/queue', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				type: 'addqueue',
				user_id: 'U_123',
				track
			})
		});
	});
});
