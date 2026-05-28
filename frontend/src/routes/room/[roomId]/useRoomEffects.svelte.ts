import { browser } from '$app/environment';
import { recordRecentRoom } from '$lib/session/recentRooms';
import { displayNameForUser } from '$lib/stores/room';
import type { LastActivityDto, RoomStateDto } from '$lib/types/api';
import { toast } from 'svelte-sonner';
import {
	appendLastActivityFromRoomState,
	HOST_TRANSFER_EVENTS,
	REPLAY_SUCCESS_EVENTS
} from './roomPageActivity';
import type { useHostPlayback } from './useHostPlayback.svelte';

export type UseRoomEffectsDeps = {
	getSessionUser: () => { userId: string; displayName: string } | null;
	getRoomUi: () => { roomState: RoomStateDto | null };
	hostPlayback: ReturnType<typeof useHostPlayback>;
	getActivityState: () => {
		activityLog: LastActivityDto[];
		activityLogRoomId: string | null;
		lastActivitySignature: string | undefined;
	};
	setActivityState: (next: {
		activityLog: LastActivityDto[];
		activityLogRoomId: string | null;
		lastActivitySignature: string | undefined;
	}) => void;
	clearHostTransferBusy: () => void;
};

export function useRoomEffects(deps: UseRoomEffectsDeps) {
	let recordedRecentThisMount = false;
	let lastReplayEventSignature = $state<string | undefined>(undefined);
	let lastHostTransferEventSignature = $state<string | undefined>(undefined);

	$effect(() => {
		if (!browser) return;
		const rs = deps.getRoomUi().roomState;
		const su = deps.getSessionUser();
		if (recordedRecentThisMount || !rs || !su) return;
		recordedRecentThisMount = true;
		recordRecentRoom({
			joinCode: rs.room.joinCode,
			name: rs.room.name,
			isHost: rs.host.userId === su.userId
		});
	});

	$effect(() => {
		if (!browser) return;
		const ev = deps.getRoomUi().roomState?.lastEvent;
		const sig = ev ? `${ev.type}:${ev.at}` : '';
		const prev = lastReplayEventSignature;
		lastReplayEventSignature = sig;
		if (ev && REPLAY_SUCCESS_EVENTS.has(ev.type) && prev !== undefined && sig !== prev) {
			toast.success(
				'The group voted to replay this track. It has been added to the top of the queue.'
			);
		}
	});

	$effect(() => {
		if (!browser) return;
		const rs = deps.getRoomUi().roomState;
		const su = deps.getSessionUser();
		const ev = rs?.lastEvent;
		const sig = ev ? `${ev.type}:${ev.at}` : '';
		const prev = lastHostTransferEventSignature;
		const prevHostId = deps.hostPlayback.getLastKnownHostUserId();

		if (rs?.transfer) {
			deps.clearHostTransferBusy();
		}

		if (ev && HOST_TRANSFER_EVENTS.has(ev.type) && prev !== undefined && sig !== prev && su && rs) {
			if (ev.type === 'host_transfer_completed') {
				if (rs.host.userId === su.userId && prevHostId !== su.userId) {
					toast.success('You are now the room host.');
				} else if (prevHostId === su.userId && rs.host.userId !== su.userId) {
					toast.message(
						'Host role transferred to ' + displayNameForUser(rs, rs.host.userId) + '.'
					);
				}
			} else if (ev.type === 'host_transfer_rejected' && rs.host.userId === su.userId) {
				toast.message('Host transfer was declined.');
			}
		}

		lastHostTransferEventSignature = sig;
	});

	$effect(() => {
		if (!browser) return;
		const rs = deps.getRoomUi().roomState;
		const su = deps.getSessionUser();
		if (!rs || !su) return;
		deps.hostPlayback.syncHostRole(su.userId);
	});

	function syncActivityFromRoomState(roomState: RoomStateDto | null): void {
		const next = appendLastActivityFromRoomState(deps.getActivityState(), roomState);
		deps.setActivityState(next);
	}

	return { syncActivityFromRoomState };
}
