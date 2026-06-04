import { apiClient } from '$lib/api/client';
import { isJoinFailureForRemovedRoom, removeRecentRoom } from '$lib/session/recentRooms';
import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';

export type JoinRoomByCodeSuccess = { ok: true; roomId: string };
export type JoinRoomByCodeFailure = { ok: false; message: string };
export type JoinRoomByCodeResult = JoinRoomByCodeSuccess | JoinRoomByCodeFailure;

/** REST join by 6-character code; persists display name and prunes stale recent-room entries. */
export async function joinRoomByCode(
	joinCode: string,
	displayName: string
): Promise<JoinRoomByCodeResult> {
	const trimmed = displayName.trim();
	if (!trimmed) {
		return { ok: false, message: 'Please enter your display name.' };
	}

	const normalizedCode = joinCode.replace(/\s/g, '').toUpperCase();
	saveSessionDisplayName(trimmed);
	const { userId } = getOrCreateSessionUser();

	try {
		const res = await apiClient.joinRoom({
			join_code: normalizedCode,
			user_id: userId,
			display_name: trimmed
		});

		if (!res.success || !res.room_id) {
			const message = res.message || 'Could not join this room.';
			if (isJoinFailureForRemovedRoom(message)) {
				removeRecentRoom(normalizedCode);
			}
			return { ok: false, message };
		}

		return { ok: true, roomId: res.room_id };
	} catch (err: unknown) {
		const message = err instanceof Error ? err.message : 'Could not join this room.';
		if (isJoinFailureForRemovedRoom(message)) {
			removeRecentRoom(normalizedCode);
		}
		return { ok: false, message: message || 'Could not join this room.' };
	}
}
