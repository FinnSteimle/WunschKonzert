export { generateRandomDisplayName } from './nameGenerator';

const USER_ID_KEY = 'wk_user_id';
const DISPLAY_NAME_KEY = 'wk_display_name';

function randomId(prefix: string, length: number): string {
	const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
	let out = prefix;
	for (let i = 0; i < length; i += 1) {
		out += alphabet[Math.floor(Math.random() * alphabet.length)];
	}
	return out;
}

export interface SessionUser {
	userId: string;
	displayName: string;
}

export function getOrCreateSessionUser(): SessionUser {
	if (typeof window === 'undefined') {
		return {
			userId: randomId('U_', 10),
			displayName: ''
		};
	}

	let userId = localStorage.getItem(USER_ID_KEY);
	let displayName = localStorage.getItem(DISPLAY_NAME_KEY);
	if (!userId) {
		userId = randomId('U_', 10);
		localStorage.setItem(USER_ID_KEY, userId);
	}
	if (!displayName) {
		displayName = '';
	}

	return { userId, displayName };
}

/** Persist display name for this browser session (create/join flows). */
export function saveSessionDisplayName(displayName: string): void {
	if (typeof window === 'undefined') return;
	const trimmed = displayName.trim();
	if (!trimmed) return;
	localStorage.setItem(DISPLAY_NAME_KEY, trimmed);
}
