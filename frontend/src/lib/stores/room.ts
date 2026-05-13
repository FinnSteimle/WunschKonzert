import { writable } from 'svelte/store';
import type { QueueEntryDto, ReplayVoteStateDto, RoomStateDto } from '$lib/types/api';

export interface RoomUiState {
	roomState: RoomStateDto | null;
	loading: boolean;
	error: string | null;
	connected: boolean;
}

const initialState: RoomUiState = {
	roomState: null,
	loading: false,
	error: null,
	connected: false
};

function createRoomStore() {
	const { subscribe, update, set } = writable<RoomUiState>(initialState);

	return {
		subscribe,
		reset: () => set(initialState),
		setLoading: (loading: boolean) => update((state) => ({ ...state, loading })),
		setError: (error: string | null) => update((state) => ({ ...state, error })),
		setConnected: (connected: boolean) => update((state) => ({ ...state, connected })),
		setRoomState: (roomState: RoomStateDto) =>
			update((state) => ({ ...state, roomState, error: null, loading: false }))
	};
}

export const roomStore = createRoomStore();

export function getPersonalVoteState(
	queueEntry: QueueEntryDto,
	userId: string
): 'upvote' | 'downvote' | 'neutral' {
	const vote = queueEntry.feedback.find((feedback) => feedback.userId === userId);
	if (!vote) return 'neutral';
	// skip / replay — treat as neutral for the upvote/downvote UI
	if (vote.type === 'skip' || vote.type === 'replay') return 'neutral';
	return vote.type;
}

/** Track IDs still active in queue (anything not finished as `played`). */
export function activeQueuedTrackIds(state: RoomStateDto | null): Set<string> {
	if (!state) return new Set();
	return new Set(state.queue.filter((e) => e.status !== 'played').map((e) => e.track.trackId));
}

export function queueWithoutCurrent(state: RoomStateDto | null): QueueEntryDto[] {
	if (!state) return [];
	const currentId = state.playback?.currentQueueEntryId;
	return currentId
		? state.queue.filter((e) => e.queueEntryId !== currentId)
		: state.queue.filter((e) => e.status !== 'playing');
}

export function getCurrentSong(roomState: RoomStateDto | null): QueueEntryDto | null {
	if (!roomState) return null;
	const playbackId = roomState.playback?.currentQueueEntryId;
	if (playbackId) {
		const matching = roomState.queue.find((entry) => entry.queueEntryId === playbackId);
		if (matching) return matching;
	}
	return roomState.queue.find((entry) => entry.status === 'playing') ?? roomState.queue[0] ?? null;
}

/** Members currently in the room (replay majority denominator). */
export function countActiveRoomMembers(roomState: RoomStateDto | null): number {
	if (!roomState) return 0;
	return roomState.users.filter(
		(u) => u.membership.leftAt === null && u.membership.membershipStatus === 'active'
	).length;
}

/** Minimum votes for strict majority (>50%) of active listeners; backend should match. */
export function replayMajorityThreshold(activeUserCount: number): number {
	if (activeUserCount <= 0) return 1;
	return Math.floor(activeUserCount / 2) + 1;
}

/**
 * Client-side replay vote panel when server omits `replayVote` but API still stores
 * `replay` feedback on the current playback entry (WS `vote` + `vote_type: replay`).
 */
export function clientReplayVoteFromPlayingEntry(
	entry: QueueEntryDto,
	roomState: RoomStateDto,
	positionMs: number,
	durationMs: number
): ReplayVoteStateDto | null {
	const currentId = roomState.playback?.currentQueueEntryId;
	if (!currentId || currentId !== entry.queueEntryId) return null;
	if (roomState.playback?.state === 'stopped') return null;

	const replayFeedback = entry.feedback.filter((f) => f.type === 'replay');
	const active = countActiveRoomMembers(roomState);
	const remainingMs = durationMs > 0 ? Math.max(0, durationMs - positionMs) : 24 * 60 * 60 * 1000;
	const closesAt = new Date(Date.now() + remainingMs).toISOString();

	return {
		targetQueueEntryId: entry.queueEntryId,
		track: entry.track,
		voteCount: replayFeedback.length,
		voterUserIds: replayFeedback.map((f) => f.userId),
		activeUserCount: active,
		closesAt,
		status: 'open'
	};
}
