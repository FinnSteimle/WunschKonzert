import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';

describe('apiClient.createRoom', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it('posts create-room payload to the expected endpoint', async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				success: true,
				message: 'ok',
				room_id: 'room-1',
				join_code: 'AB2CD3'
			})
		});
		vi.stubGlobal('fetch', fetchMock);

		const payload = {
			name: 'Friday vibes',
			user_id: 'U_TESTUSER1',
			display_name: 'Alice',
			supported_provider_id: 'spotify' as const
		};

		await apiClient.createRoom(payload);

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

	it('falls back to status text when error response is not parseable JSON', async () => {
		const fetchMock = vi.fn().mockResolvedValue({
			ok: false,
			status: 503,
			json: async () => {
				throw new Error('not json');
			}
		});
		vi.stubGlobal('fetch', fetchMock);

		await expect(
			apiClient.createRoom({
				name: 'Friday vibes',
				user_id: 'U_TESTUSER1',
				display_name: 'Alice',
				supported_provider_id: 'spotify'
			})
		).rejects.toThrow('Request failed: 503');
	});
});
