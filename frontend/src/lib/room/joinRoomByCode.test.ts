import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '$lib/api/client';
import { isJoinFailureForRemovedRoom, removeRecentRoom } from '$lib/session/recentRooms';
import { joinRoomByCode } from './joinRoomByCode';

vi.mock('$lib/api/client', () => ({
	apiClient: {
		joinRoom: vi.fn()
	}
}));

vi.mock('$lib/session/recentRooms', () => ({
	isJoinFailureForRemovedRoom: vi.fn(),
	removeRecentRoom: vi.fn()
}));

describe('joinRoomByCode', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		localStorage.clear();
		vi.mocked(isJoinFailureForRemovedRoom).mockReturnValue(false);
	});

	it('returns failure when display name is empty', async () => {
		const result = await joinRoomByCode('AB2CD3', '   ');
		expect(result).toEqual({ ok: false, message: 'Please enter your display name.' });
		expect(apiClient.joinRoom).not.toHaveBeenCalled();
	});

	it('returns room id on successful join', async () => {
		vi.mocked(apiClient.joinRoom).mockResolvedValue({
			success: true,
			room_id: 'room-uuid',
			message: 'ok'
		});

		const result = await joinRoomByCode('ab2cd3', 'Alice');

		expect(result).toEqual({ ok: true, roomId: 'room-uuid' });
		expect(apiClient.joinRoom).toHaveBeenCalledWith({
			join_code: 'AB2CD3',
			user_id: expect.stringMatching(/^U_/),
			display_name: 'Alice'
		});
		expect(localStorage.getItem('wk_display_name')).toBe('Alice');
	});

	it('returns failure message when join API reports failure', async () => {
		vi.mocked(apiClient.joinRoom).mockResolvedValue({
			success: false,
			message: 'Room not found'
		});

		const result = await joinRoomByCode('AB2CD3', 'Bob');

		expect(result).toEqual({ ok: false, message: 'Room not found' });
	});

	it('removes stale recent room when join failure indicates removed room', async () => {
		vi.mocked(apiClient.joinRoom).mockResolvedValue({
			success: false,
			message: 'Room not found'
		});
		vi.mocked(isJoinFailureForRemovedRoom).mockReturnValue(true);

		await joinRoomByCode('ab2cd3', 'Bob');

		expect(removeRecentRoom).toHaveBeenCalledWith('AB2CD3');
	});

	it('returns failure when success is true but room_id is missing', async () => {
		vi.mocked(apiClient.joinRoom).mockResolvedValue({
			success: true,
			message: 'ok'
		});

		const result = await joinRoomByCode('AB2CD3', 'Bob');

		expect(result).toEqual({ ok: false, message: 'ok' });
	});

	it('maps network errors to failure result', async () => {
		vi.mocked(apiClient.joinRoom).mockRejectedValue(new Error('Network down'));

		const result = await joinRoomByCode('AB2CD3', 'Bob');

		expect(result).toEqual({ ok: false, message: 'Network down' });
	});

	it('removes recent room when thrown error indicates removed room', async () => {
		vi.mocked(apiClient.joinRoom).mockRejectedValue(new Error('Room not found'));
		vi.mocked(isJoinFailureForRemovedRoom).mockReturnValue(true);

		await joinRoomByCode('AB2CD3', 'Bob');

		expect(removeRecentRoom).toHaveBeenCalledWith('AB2CD3');
	});
});
