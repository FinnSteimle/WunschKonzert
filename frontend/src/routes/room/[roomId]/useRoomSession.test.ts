import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { goto } from '$app/navigation';
import { removeRecentRoom } from '$lib/session/recentRooms';
import { roomStore } from '$lib/stores/room';
import type { RoomStateDto } from '$lib/types/api';
import { toast } from 'svelte-sonner';
import { createBeginRoomSession } from './useRoomSession.svelte';

const { mockConnect, mockDisconnect } = vi.hoisted(() => ({
	mockConnect: vi.fn(),
	mockDisconnect: vi.fn()
}));

vi.mock('$lib/realtime/roomSocket', () => ({
	RoomSocketClient: class RoomSocketClientMock {
		connect = mockConnect;
		disconnect = mockDisconnect;
		constructor(
			public roomId: string,
			public handlers: unknown,
			public userId: string | null
		) {}
	}
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: vi.fn((path: string) => path)
}));

vi.mock('$lib/session/recentRooms', () => ({
	removeRecentRoom: vi.fn()
}));

vi.mock('svelte-sonner', () => ({
	toast: {
		error: vi.fn(),
		message: vi.fn()
	}
}));

function minimalRoomState(overrides: Partial<RoomStateDto['room']> = {}): RoomStateDto {
	return {
		room: {
			roomId: 'room-1',
			joinCode: 'AB2CD3',
			name: 'Test',
			status: 'active',
			supportedProviderId: 'spotify',
			...overrides
		},
		host: { userId: 'U_HOST', displayName: 'Host', createdAt: '2025-01-01T00:00:00Z' },
		users: [],
		queue: [],
		playback: undefined,
		lastEvent: undefined,
		transfer: undefined
	} as RoomStateDto;
}

describe('createBeginRoomSession', () => {
	const hostPlayback = {
		maybeInitHostPlayer: vi.fn(),
		teardownHostPlayback: vi.fn()
	};

	beforeEach(() => {
		vi.clearAllMocks();
		roomStore.reset();
	});

	it('creates socket, connects, and tears down on cleanup', () => {
		const setSocketClient = vi.fn();
		const syncActivity = vi.fn();

		const begin = createBeginRoomSession({
			getSessionUser: () => ({ userId: 'U_GUEST', displayName: 'Guest' }),
			setSocketClient,
			hostPlayback,
			syncActivityFromRoomState: syncActivity
		});

		const teardown = begin('room-uuid');

		expect(setSocketClient).toHaveBeenCalled();
		expect(mockConnect).toHaveBeenCalled();
		expect(get(roomStore).loading).toBe(true);

		teardown();

		expect(mockDisconnect).toHaveBeenCalled();
		expect(setSocketClient).toHaveBeenLastCalledWith(null);
		expect(hostPlayback.teardownHostPlayback).toHaveBeenCalled();
		expect(get(roomStore).roomState).toBeNull();
	});

	it('syncs activity and initializes host player when room state updates', () => {
		const syncActivity = vi.fn();
		const begin = createBeginRoomSession({
			getSessionUser: () => ({ userId: 'U_HOST', displayName: 'Host' }),
			setSocketClient: vi.fn(),
			hostPlayback,
			syncActivityFromRoomState: syncActivity
		});

		begin('room-uuid');
		const state = minimalRoomState();
		roomStore.setRoomState(state);

		expect(syncActivity).toHaveBeenCalledWith(state);
		expect(hostPlayback.maybeInitHostPlayer).toHaveBeenCalledWith(
			'U_HOST',
			'U_HOST',
			'spotify'
		);
	});

	it('redirects guests when room is deleted', () => {
		const begin = createBeginRoomSession({
			getSessionUser: () => ({ userId: 'U_GUEST', displayName: 'Guest' }),
			setSocketClient: vi.fn(),
			hostPlayback,
			syncActivityFromRoomState: vi.fn()
		});

		begin('room-uuid');
		roomStore.setRoomState(minimalRoomState({ status: 'deleted' }));

		expect(removeRecentRoom).toHaveBeenCalledWith('AB2CD3');
		expect(toast.message).toHaveBeenCalledWith('Room ended by host');
		expect(goto).toHaveBeenCalledWith('/');
	});

	it('does not toast guests when host deletes room and viewer is host', () => {
		const begin = createBeginRoomSession({
			getSessionUser: () => ({ userId: 'U_HOST', displayName: 'Host' }),
			setSocketClient: vi.fn(),
			hostPlayback,
			syncActivityFromRoomState: vi.fn()
		});

		begin('room-uuid');
		roomStore.setRoomState(minimalRoomState({ status: 'deleted' }));

		expect(removeRecentRoom).toHaveBeenCalledWith('AB2CD3');
		expect(toast.message).not.toHaveBeenCalled();
		expect(goto).toHaveBeenCalledWith('/');
	});
});
