import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	getRecentRooms,
	isJoinFailureForRemovedRoom,
	recordRecentRoom,
	removeRecentRoom,
	syncRecentRoomsAvailability
} from './recentRooms';

describe('recentRooms', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.restoreAllMocks();
	});

	it('records and normalizes a recent room entry', () => {
		const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(1_700_000_000_000);

		recordRecentRoom({ joinCode: ' ab 2cd3 ', name: '  My Room  ', isHost: true });

		expect(getRecentRooms()).toEqual([
			{
				joinCode: 'AB2CD3',
				name: 'My Room',
				isHost: true,
				visitedAt: 1_700_000_000_000
			}
		]);

		nowSpy.mockRestore();
	});

	it('de-duplicates by join code and keeps newest first', () => {
		const nowSpy = vi
			.spyOn(Date, 'now')
			.mockReturnValueOnce(1)
			.mockReturnValueOnce(2)
			.mockReturnValueOnce(3);

		recordRecentRoom({ joinCode: 'AB2CD3', name: 'First', isHost: false });
		recordRecentRoom({ joinCode: 'ZX9WV8', name: 'Second', isHost: true });
		recordRecentRoom({ joinCode: 'ab2cd3', name: 'Updated', isHost: true });

		expect(getRecentRooms()).toEqual([
			{ joinCode: 'AB2CD3', name: 'Updated', isHost: true, visitedAt: 3 },
			{ joinCode: 'ZX9WV8', name: 'Second', isHost: true, visitedAt: 2 }
		]);

		nowSpy.mockRestore();
	});

	it('keeps at most five entries', () => {
		const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(10);

		for (let i = 0; i < 7; i += 1) {
			recordRecentRoom({ joinCode: `AB2CD${i + 2}`, name: `Room ${i + 1}`, isHost: false });
		}

		expect(getRecentRooms()).toHaveLength(5);

		nowSpy.mockRestore();
	});

	it('filters malformed storage data and falls back safely', () => {
		localStorage.setItem(
			'wk_recent_rooms',
			JSON.stringify([
				{ joinCode: ' ab2cd3 ', name: '', isHost: true, visitedAt: 42 },
				{ joinCode: '', name: 'No code', isHost: false, visitedAt: 1 },
				{ joinCode: 'ZX9WV8', name: 'ok', isHost: 'yes', visitedAt: 'bad' }
			])
		);

		expect(getRecentRooms()).toEqual([
			{ joinCode: 'AB2CD3', name: 'Room', isHost: true, visitedAt: 42 },
			{ joinCode: 'ZX9WV8', name: 'ok', isHost: false, visitedAt: 0 }
		]);

		localStorage.setItem('wk_recent_rooms', '{invalid-json');
		expect(getRecentRooms()).toEqual([]);
	});

	it('removes a room by normalized join code', () => {
		localStorage.setItem(
			'wk_recent_rooms',
			JSON.stringify([
				{ joinCode: 'AB2CD3', name: 'A', isHost: true, visitedAt: 1 },
				{ joinCode: 'ZX9WV8', name: 'B', isHost: false, visitedAt: 2 }
			])
		);

		removeRecentRoom(' ab2 cd3 ');

		expect(getRecentRooms()).toEqual([{ joinCode: 'ZX9WV8', name: 'B', isHost: false, visitedAt: 2 }]);
	});

	it('keeps only available recent rooms after backend sync', async () => {
		localStorage.setItem(
			'wk_recent_rooms',
			JSON.stringify([
				{ joinCode: 'AB2CD3', name: 'A', isHost: true, visitedAt: 1 },
				{ joinCode: 'ZX9WV8', name: 'B', isHost: false, visitedAt: 2 }
			])
		);

		const fetchMock = vi.fn().mockResolvedValue({
			ok: true,
			json: async () => ({
				available_join_codes: ['ZX9WV8'],
				unavailable_join_codes: ['AB2CD3']
			})
		});
		vi.stubGlobal('fetch', fetchMock);

		const synced = await syncRecentRoomsAvailability();

		expect(fetchMock).toHaveBeenCalledOnce();
		expect(synced).toEqual([{ joinCode: 'ZX9WV8', name: 'B', isHost: false, visitedAt: 2 }]);
		expect(getRecentRooms()).toEqual([{ joinCode: 'ZX9WV8', name: 'B', isHost: false, visitedAt: 2 }]);
	});

	it('keeps local recent rooms when availability request fails', async () => {
		localStorage.setItem(
			'wk_recent_rooms',
			JSON.stringify([{ joinCode: 'AB2CD3', name: 'A', isHost: true, visitedAt: 1 }])
		);

		const fetchMock = vi.fn().mockRejectedValue(new Error('network down'));
		vi.stubGlobal('fetch', fetchMock);

		const synced = await syncRecentRoomsAvailability();

		expect(fetchMock).toHaveBeenCalledOnce();
		expect(synced).toEqual([{ joinCode: 'AB2CD3', name: 'A', isHost: true, visitedAt: 1 }]);
		expect(getRecentRooms()).toEqual([{ joinCode: 'AB2CD3', name: 'A', isHost: true, visitedAt: 1 }]);
	});
});

describe('isJoinFailureForRemovedRoom', () => {
	it('detects backend messages indicating missing or closed rooms', () => {
		expect(isJoinFailureForRemovedRoom('Room not found')).toBe(true);
		expect(isJoinFailureForRemovedRoom('room is not active')).toBe(true);
		expect(isJoinFailureForRemovedRoom('Session has ended.')).toBe(true);
		expect(isJoinFailureForRemovedRoom('request failed: 404 Not Found')).toBe(true);
	});

	it('returns false for unrelated messages', () => {
		expect(isJoinFailureForRemovedRoom('validation failed')).toBe(false);
		expect(isJoinFailureForRemovedRoom('')).toBe(false);
	});
});
