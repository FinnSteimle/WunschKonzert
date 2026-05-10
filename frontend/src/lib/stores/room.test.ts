import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import {
	roomStore,
	getPersonalVoteState,
	getCurrentSong,
	queueWithoutCurrent,
	activeQueuedTrackIds,
	countActiveRoomMembers,
	replayMajorityThreshold,
	clientReplayVoteFromPlayingEntry,
	type RoomUiState
} from './room';
import type { QueueEntryDto, RoomStateDto } from '$lib/types/api';

function makeQueueEntry(overrides: Partial<QueueEntryDto> = {}): QueueEntryDto {
	return {
		queueEntryId: 'q1',
		track: {
			trackId: 't1',
			providerTrackId: 'spotify:t1',
			title: 'Song',
			artist: 'Artist',
			album: 'Album',
			duration: 200_000,
			coverUrl: 'https://example.com/cover.jpg',
			deepLink: 'https://example.com/track/t1'
		},
		addedBy: { userId: 'user-1', displayName: 'Alice' },
		queuedAt: '2025-01-01T00:00:00Z',
		position: 0,
		status: 'queued',
		voteScore: 3,
		orderRank: 0,
		feedback: [],
		...overrides
	};
}

function makeRoomState(overrides: Partial<RoomStateDto> = {}): RoomStateDto {
	return {
		room: {
			roomId: 'room-1',
			joinCode: 'AB2CD3',
			name: 'Test Room',
			status: 'active',
			createdAt: '2025-01-01T00:00:00Z'
		},
		host: {
			userId: 'host-1',
			displayName: 'Host',
			createdAt: '2025-01-01T00:00:00Z'
		},
		users: [],
		queue: [],
		...overrides
	};
}

describe('roomStore', () => {
	beforeEach(() => {
		roomStore.reset();
	});

	it('has correct initial state', () => {
		const state = get(roomStore);
		expect(state).toEqual({
			roomState: null,
			loading: false,
			error: null,
			connected: false
		});
	});

	it('setLoading updates only the loading flag', () => {
		roomStore.setLoading(true);
		expect(get(roomStore).loading).toBe(true);
		expect(get(roomStore).error).toBeNull();
	});

	it('setError updates only the error field', () => {
		roomStore.setError('Something broke');
		const state = get(roomStore);
		expect(state.error).toBe('Something broke');
		expect(state.loading).toBe(false);
	});

	it('setConnected updates only the connected flag', () => {
		roomStore.setConnected(true);
		expect(get(roomStore).connected).toBe(true);
	});

	it('setRoomState sets state and clears error and loading', () => {
		roomStore.setLoading(true);
		roomStore.setError('old error');

		const rs = makeRoomState();
		roomStore.setRoomState(rs);

		const state = get(roomStore);
		expect(state.roomState).toBe(rs);
		expect(state.error).toBeNull();
		expect(state.loading).toBe(false);
	});

	it('reset brings back initial state', () => {
		roomStore.setConnected(true);
		roomStore.setLoading(true);
		roomStore.setRoomState(makeRoomState());

		roomStore.reset();

		expect(get(roomStore)).toEqual({
			roomState: null,
			loading: false,
			error: null,
			connected: false
		});
	});

	it('notifies subscribers on every update', () => {
		const snapshots: RoomUiState[] = [];
		const unsub = roomStore.subscribe((s) => snapshots.push({ ...s }));

		roomStore.setLoading(true);
		roomStore.setConnected(true);
		roomStore.reset();

		unsub();
		// initial + 3 updates
		expect(snapshots.length).toBe(4);
		expect(snapshots[1].loading).toBe(true);
		expect(snapshots[2].connected).toBe(true);
		expect(snapshots[3].loading).toBe(false);
	});
});

describe('getPersonalVoteState', () => {
	it('returns neutral when user has no feedback', () => {
		const entry = makeQueueEntry({ feedback: [] });
		expect(getPersonalVoteState(entry, 'user-1')).toBe('neutral');
	});

	it('returns upvote when user has upvoted', () => {
		const entry = makeQueueEntry({
			feedback: [{ userId: 'user-1', votedAt: '2025-01-01T00:00:00Z', type: 'upvote' }]
		});
		expect(getPersonalVoteState(entry, 'user-1')).toBe('upvote');
	});

	it('returns downvote when user has downvoted', () => {
		const entry = makeQueueEntry({
			feedback: [{ userId: 'user-1', votedAt: '2025-01-01T00:00:00Z', type: 'downvote' }]
		});
		expect(getPersonalVoteState(entry, 'user-1')).toBe('downvote');
	});

	it('ignores other users feedback', () => {
		const entry = makeQueueEntry({
			feedback: [
				{ userId: 'user-2', votedAt: '2025-01-01T00:00:00Z', type: 'upvote' },
				{ userId: 'user-3', votedAt: '2025-01-01T00:00:00Z', type: 'downvote' }
			]
		});
		expect(getPersonalVoteState(entry, 'user-1')).toBe('neutral');
	});

	it('finds correct user among multiple feedback entries', () => {
		const entry = makeQueueEntry({
			feedback: [
				{ userId: 'user-2', votedAt: '2025-01-01T00:00:00Z', type: 'upvote' },
				{ userId: 'user-1', votedAt: '2025-01-01T00:00:00Z', type: 'downvote' },
				{ userId: 'user-3', votedAt: '2025-01-01T00:00:00Z', type: 'upvote' }
			]
		});
		expect(getPersonalVoteState(entry, 'user-1')).toBe('downvote');
	});

	it('treats replay feedback as neutral for queue upvote UI', () => {
		const entry = makeQueueEntry({
			feedback: [{ userId: 'user-1', votedAt: '2025-01-01T00:00:00Z', type: 'replay' }]
		});
		expect(getPersonalVoteState(entry, 'user-1')).toBe('neutral');
	});
});

describe('activeQueuedTrackIds', () => {
	it('returns empty set for null state', () => {
		expect(activeQueuedTrackIds(null)).toEqual(new Set());
	});

	it('includes playing and queued tracks, excludes played', () => {
		const played = makeQueueEntry({
			queueEntryId: 'q-old',
			status: 'played',
			track: { ...makeQueueEntry().track, trackId: 't-played' }
		});
		const playing = makeQueueEntry({
			queueEntryId: 'q-now',
			status: 'playing',
			track: { ...makeQueueEntry().track, trackId: 't-now' }
		});
		const queued = makeQueueEntry({
			queueEntryId: 'q-next',
			status: 'queued',
			track: { ...makeQueueEntry().track, trackId: 't-next' }
		});
		const state = makeRoomState({ queue: [played, playing, queued] });
		expect(activeQueuedTrackIds(state)).toEqual(new Set(['t-now', 't-next']));
	});
});

describe('queueWithoutCurrent', () => {
	it('returns empty array for null state', () => {
		expect(queueWithoutCurrent(null)).toEqual([]);
	});

	it('filters out entry matching playback currentQueueEntryId', () => {
		const playing = makeQueueEntry({ queueEntryId: 'q1', status: 'playing' });
		const queued = makeQueueEntry({ queueEntryId: 'q2', status: 'queued' });
		const state = makeRoomState({
			queue: [playing, queued],
			playback: {
				state: 'playing',
				currentQueueEntryId: 'q1',
				updatedAt: '2025-01-01T00:00:00Z',
				positionMs: 0
			}
		});
		expect(queueWithoutCurrent(state)).toEqual([queued]);
	});

	it('filters out entry with status playing when no playback id', () => {
		const playing = makeQueueEntry({ queueEntryId: 'q1', status: 'playing' });
		const queued = makeQueueEntry({ queueEntryId: 'q2', status: 'queued' });
		const state = makeRoomState({ queue: [playing, queued] });
		expect(queueWithoutCurrent(state)).toEqual([queued]);
	});

	it('returns all entries when none is playing and no playback id', () => {
		const a = makeQueueEntry({ queueEntryId: 'q1', status: 'queued' });
		const b = makeQueueEntry({ queueEntryId: 'q2', status: 'queued' });
		const state = makeRoomState({ queue: [a, b] });
		expect(queueWithoutCurrent(state)).toEqual([a, b]);
	});

	it('returns empty array for empty queue', () => {
		expect(queueWithoutCurrent(makeRoomState({ queue: [] }))).toEqual([]);
	});
});

describe('getCurrentSong', () => {
	it('returns null for null roomState', () => {
		expect(getCurrentSong(null)).toBeNull();
	});

	it('returns null for empty queue', () => {
		expect(getCurrentSong(makeRoomState({ queue: [] }))).toBeNull();
	});

	it('returns entry matching playback currentQueueEntryId', () => {
		const entry = makeQueueEntry({ queueEntryId: 'q42', status: 'queued' });
		const state = makeRoomState({
			queue: [makeQueueEntry({ queueEntryId: 'q1' }), entry],
			playback: {
				state: 'playing',
				currentQueueEntryId: 'q42',
				updatedAt: '2025-01-01T00:00:00Z',
				positionMs: 5000
			}
		});
		expect(getCurrentSong(state)).toBe(entry);
	});

	it('falls back to entry with status playing when playback id does not match', () => {
		const playing = makeQueueEntry({ queueEntryId: 'q2', status: 'playing' });
		const state = makeRoomState({
			queue: [makeQueueEntry({ queueEntryId: 'q1', status: 'queued' }), playing],
			playback: {
				state: 'playing',
				currentQueueEntryId: 'q-missing',
				updatedAt: '2025-01-01T00:00:00Z',
				positionMs: 0
			}
		});
		expect(getCurrentSong(state)).toBe(playing);
	});

	it('falls back to first queue entry when no playing entry exists', () => {
		const first = makeQueueEntry({ queueEntryId: 'q1', status: 'queued' });
		const state = makeRoomState({
			queue: [first, makeQueueEntry({ queueEntryId: 'q2', status: 'queued' })]
		});
		expect(getCurrentSong(state)).toBe(first);
	});

	it('returns playing entry when there is no playback object', () => {
		const playing = makeQueueEntry({ queueEntryId: 'q2', status: 'playing' });
		const state = makeRoomState({
			queue: [makeQueueEntry({ queueEntryId: 'q1', status: 'queued' }), playing]
		});
		expect(getCurrentSong(state)).toBe(playing);
	});

	it('returns null when playback.currentQueueEntryId is null and no playing entry', () => {
		const state = makeRoomState({
			queue: [],
			playback: {
				state: 'stopped',
				currentQueueEntryId: null,
				updatedAt: '2025-01-01T00:00:00Z',
				positionMs: 0
			}
		});
		expect(getCurrentSong(state)).toBeNull();
	});
});

describe('countActiveRoomMembers', () => {
	it('counts users with active membership and no leftAt', () => {
		const state = makeRoomState({
			users: [
				{
					user: { userId: 'u1', displayName: 'A', createdAt: '2025-01-01T00:00:00Z' },
					membership: { joinedAt: '2025-01-01T00:00:00Z', leftAt: null, membershipStatus: 'active' }
				},
				{
					user: { userId: 'u2', displayName: 'B', createdAt: '2025-01-01T00:00:00Z' },
					membership: {
						joinedAt: '2025-01-01T00:00:00Z',
						leftAt: '2025-01-02T00:00:00Z',
						membershipStatus: 'active'
					}
				}
			]
		});
		expect(countActiveRoomMembers(state)).toBe(1);
	});

	it('returns 0 for null state', () => {
		expect(countActiveRoomMembers(null)).toBe(0);
	});
});

describe('clientReplayVoteFromPlayingEntry', () => {
	it('returns null when playback is stopped', () => {
		const entry = makeQueueEntry({ queueEntryId: 'qx', status: 'playing' });
		const state = makeRoomState({
			queue: [entry],
			users: [
				{
					user: { userId: 'u1', displayName: 'A', createdAt: '2025-01-01T00:00:00Z' },
					membership: { joinedAt: '2025-01-01T00:00:00Z', leftAt: null, membershipStatus: 'active' }
				}
			],
			playback: {
				state: 'stopped',
				currentQueueEntryId: 'qx',
				updatedAt: '2025-01-01T00:00:00Z',
				positionMs: 0
			}
		});
		expect(clientReplayVoteFromPlayingEntry(entry, state, 0, 60_000)).toBeNull();
	});

	it('returns open replay state with vote tally from feedback', () => {
		const entry = makeQueueEntry({
			queueEntryId: 'qx',
			status: 'playing',
			feedback: [
				{
					userId: 'u1',
					votedAt: '2025-01-01T00:00:00Z',
					type: 'replay' as const
				}
			]
		});
		const state = makeRoomState({
			queue: [entry],
			users: [
				{
					user: { userId: 'u1', displayName: 'A', createdAt: '2025-01-01T00:00:00Z' },
					membership: { joinedAt: '2025-01-01T00:00:00Z', leftAt: null, membershipStatus: 'active' }
				},
				{
					user: { userId: 'u2', displayName: 'B', createdAt: '2025-01-01T00:00:00Z' },
					membership: { joinedAt: '2025-01-01T00:00:00Z', leftAt: null, membershipStatus: 'active' }
				}
			],
			playback: {
				state: 'playing',
				currentQueueEntryId: 'qx',
				updatedAt: '2025-01-01T00:00:00Z',
				positionMs: 10_000
			}
		});
		const derived = clientReplayVoteFromPlayingEntry(entry, state, 10_000, 60_000);
		expect(derived?.voteCount).toBe(1);
		expect(derived?.voterUserIds).toEqual(['u1']);
		expect(derived?.activeUserCount).toBe(2);
		expect(derived?.targetQueueEntryId).toBe('qx');
		expect(derived?.status).toBe('open');
	});

	it('returns null when entry is not current playback', () => {
		const entry = makeQueueEntry({ queueEntryId: 'qx', status: 'playing' });
		const state = makeRoomState({
			queue: [entry],
			playback: {
				state: 'playing',
				currentQueueEntryId: 'other',
				updatedAt: '2025-01-01T00:00:00Z',
				positionMs: 0
			}
		});
		expect(clientReplayVoteFromPlayingEntry(entry, state, 0, 60_000)).toBeNull();
	});
});

describe('replayMajorityThreshold', () => {
	it('uses strict majority (>50%) of active listeners', () => {
		expect(replayMajorityThreshold(1)).toBe(1);
		expect(replayMajorityThreshold(2)).toBe(2);
		expect(replayMajorityThreshold(3)).toBe(2);
		expect(replayMajorityThreshold(4)).toBe(3);
		expect(replayMajorityThreshold(5)).toBe(3);
	});

	it('defaults to 1 when count is non-positive', () => {
		expect(replayMajorityThreshold(0)).toBe(1);
		expect(replayMajorityThreshold(-1)).toBe(1);
	});
});
