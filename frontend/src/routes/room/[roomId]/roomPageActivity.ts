import type { LastActivityDto, RoomStateDto } from '$lib/types/api';

export const REPLAY_SUCCESS_EVENTS = new Set(['replay_scheduled', 'playback_replayed']);
export const HOST_TRANSFER_EVENTS = new Set([
	'host_transfer_initiated',
	'host_transfer_rejected',
	'host_transfer_completed'
]);
export const HIDDEN_ACTIVITY_TYPES = new Set(['playback_paused', 'playback_resumed']);
export const MAX_ACTIVITY_LOG_ITEMS = 100;

export function signatureForActivity(activity: LastActivityDto): string {
	return `${activity.type}:${activity.userId}:${activity.queueEntryId ?? ''}:${activity.at}`;
}

export type ActivityLogState = {
	activityLog: LastActivityDto[];
	activityLogRoomId: string | null;
	lastActivitySignature: string | undefined;
};

export function appendLastActivityFromRoomState(
	state: ActivityLogState,
	rs: RoomStateDto | null
): ActivityLogState {
	const roomId = rs?.room.roomId ?? null;
	let { activityLog, activityLogRoomId, lastActivitySignature } = state;

	if (activityLogRoomId !== roomId) {
		activityLogRoomId = roomId;
		activityLog = [];
		lastActivitySignature = undefined;
	}

	const activity = rs?.lastActivity;
	if (!activity || HIDDEN_ACTIVITY_TYPES.has(activity.type)) {
		return { activityLog, activityLogRoomId, lastActivitySignature };
	}

	const signature = signatureForActivity(activity);
	if (signature === lastActivitySignature) {
		return { activityLog, activityLogRoomId, lastActivitySignature };
	}

	lastActivitySignature = signature;
	activityLog = [
		{ ...activity },
		...activityLog.filter((item) => signatureForActivity(item) !== signature)
	].slice(0, MAX_ACTIVITY_LOG_ITEMS);

	return { activityLog, activityLogRoomId, lastActivitySignature };
}
