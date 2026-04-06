const STORAGE_KEY = 'wk_recent_rooms';
const MAX_ENTRIES = 5;

export interface RecentRoomEntry {
	joinCode: string;
	name: string;
	isHost: boolean;
	visitedAt: number;
}

function normalizeJoinCode(code: string): string {
	return code.trim().replace(/\s/g, '').toUpperCase();
}

export function recordRecentRoom(
	entry: Pick<RecentRoomEntry, 'joinCode' | 'name' | 'isHost'>
): void {
	if (typeof window === 'undefined') return;
	const joinCode = normalizeJoinCode(entry.joinCode);
	if (!joinCode) return;
	const name = entry.name.trim().slice(0, 60) || 'Room';
	const list = getRecentRooms().filter((e) => e.joinCode !== joinCode);
	const next: RecentRoomEntry = {
		joinCode,
		name,
		isHost: entry.isHost,
		visitedAt: Date.now()
	};
	localStorage.setItem(STORAGE_KEY, JSON.stringify([next, ...list].slice(0, MAX_ENTRIES)));
}

export function getRecentRooms(): RecentRoomEntry[] {
	if (typeof window === 'undefined') return [];
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return [];
		const parsed = JSON.parse(raw) as unknown;
		if (!Array.isArray(parsed)) return [];
		const out: RecentRoomEntry[] = [];
		for (const item of parsed) {
			if (!item || typeof item !== 'object') continue;
			const rec = item as Record<string, unknown>;
			const joinCode = typeof rec.joinCode === 'string' ? normalizeJoinCode(rec.joinCode) : '';
			const name = typeof rec.name === 'string' ? rec.name.slice(0, 60) : '';
			const isHost = rec.isHost === true;
			const visitedAt =
				typeof rec.visitedAt === 'number' && Number.isFinite(rec.visitedAt) ? rec.visitedAt : 0;
			if (joinCode) {
				out.push({ joinCode, name: name || 'Room', isHost, visitedAt });
			}
		}
		return out;
	} catch {
		return [];
	}
}

/** True when the room no longer exists or is not joinable (backend join/state errors). */
export function isJoinFailureForRemovedRoom(message: string): boolean {
	const m = message.trim().toLowerCase();
	if (!m) return false;
	if (m.includes('room not found')) return true;
	if (m.includes('room is not active')) return true;
	if (m.startsWith('request failed: 404')) return true;
	return false;
}

export function removeRecentRoom(joinCode: string): void {
	if (typeof window === 'undefined') return;
	const code = normalizeJoinCode(joinCode);
	if (!code) return;
	const list = getRecentRooms().filter((e) => e.joinCode !== code);
	localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}
