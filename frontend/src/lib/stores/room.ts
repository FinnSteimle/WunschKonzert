import { writable } from 'svelte/store';
import type { QueueEntryDto, RoomStateDto } from '$lib/types/api';

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

export function getPersonalVoteState(queueEntry: QueueEntryDto, userId: string): 'upvote' | 'downvote' | 'neutral' {
	const vote = queueEntry.feedback.find((feedback) => feedback.userId === userId);
	return vote?.type ?? 'neutral';
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
