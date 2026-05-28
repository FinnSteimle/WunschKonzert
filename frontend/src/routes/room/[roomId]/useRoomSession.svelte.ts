import { goto } from '$app/navigation';
import { resolve } from '$app/paths';
import { RoomSocketClient } from '$lib/realtime/roomSocket';
import { removeRecentRoom } from '$lib/session/recentRooms';
import { roomStore } from '$lib/stores/room';
import type { ProviderId, RoomStateDto } from '$lib/types/api';
import { toast } from 'svelte-sonner';

export type RoomSessionHostPlayback = {
	maybeInitHostPlayer: (
		sessionUserId: string | undefined,
		hostUserId: string | undefined,
		providerId: ProviderId | undefined
	) => void;
	teardownHostPlayback: () => void;
};

export type BeginRoomSessionDeps = {
	getSessionUser: () => { userId: string; displayName: string } | null;
	setSocketClient: (client: RoomSocketClient | null) => void;
	hostPlayback: RoomSessionHostPlayback;
	syncActivityFromRoomState: (roomState: RoomStateDto | null) => void;
};

export function createBeginRoomSession(deps: BeginRoomSessionDeps) {
	return function beginRoomSession(roomId: string): () => void {
		roomStore.reset();
		roomStore.setLoading(true);

		let roomDeletedRedirectDone = false;
		const unsubDeleted = roomStore.subscribe((ui) => {
			deps.syncActivityFromRoomState(ui.roomState);
			if (roomDeletedRedirectDone) return;
			if (ui.roomState?.room.status === 'deleted') {
				roomDeletedRedirectDone = true;
				removeRecentRoom(ui.roomState.room.joinCode);
				const sessionUser = deps.getSessionUser();
				if (sessionUser && ui.roomState.host.userId !== sessionUser.userId) {
					toast.message('Room ended by host');
				}
				void goto(resolve('/'));
			}

			const providerId = ui.roomState?.room.supportedProviderId;
			const supportedProviderId =
				providerId === 'spotify' || providerId === 'apple-music' ? providerId : undefined;
			deps.hostPlayback.maybeInitHostPlayer(
				deps.getSessionUser()?.userId,
				ui.roomState?.host.userId,
				supportedProviderId
			);
		});

		const socket = new RoomSocketClient(
			roomId,
			{
				onState: (s) => roomStore.setRoomState(s),
				onError: (m) => {
					toast.error(m);
					roomStore.setError(m);
				},
				onConnectionChange: (c) => roomStore.setConnected(c)
			},
			deps.getSessionUser()?.userId ?? null
		);
		deps.setSocketClient(socket);
		socket.connect();

		return () => {
			unsubDeleted();
			socket.disconnect();
			deps.setSocketClient(null);
			deps.hostPlayback.teardownHostPlayback();
			roomStore.reset();
		};
	};
}
