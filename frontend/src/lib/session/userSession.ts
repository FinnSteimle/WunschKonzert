const USER_ID_KEY = 'wk_user_id';
const DISPLAY_NAME_KEY = 'wk_display_name';
/** Set when the user saves a name (create/join forms or link prompt). */
const DISPLAY_NAME_EXPLICIT_KEY = 'wk_display_name_explicit';

/** Matches auto-generated guest names from {@link randomId}('Guest-', 4). */
const AUTO_GUEST_DISPLAY_NAME_RE = /^Guest-[A-HJ-NP-Z2-9]{4}$/;

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
			displayName: randomId('Guest-', 4)
		};
	}

	let userId = localStorage.getItem(USER_ID_KEY);
	let displayName = localStorage.getItem(DISPLAY_NAME_KEY);
	if (!userId) {
		userId = randomId('U_', 10);
		localStorage.setItem(USER_ID_KEY, userId);
	}
	if (!displayName) {
		displayName = randomId('Guest-', 4);
		localStorage.setItem(DISPLAY_NAME_KEY, displayName);
	}

	return { userId, displayName };
}

export function isAutoGuestDisplayName(displayName: string): boolean {
	return AUTO_GUEST_DISPLAY_NAME_RE.test(displayName.trim());
}

/**
 * When false, a join-by-link visitor may skip the name card and join immediately.
 * True for fresh auto-guest names who have never saved a name via the app.
 */
export function shouldPromptJoinLinkDisplayName(): boolean {
	if (typeof window === 'undefined') return false;
	if (localStorage.getItem(DISPLAY_NAME_EXPLICIT_KEY) === '1') return false;
	const { displayName } = getOrCreateSessionUser();
	return isAutoGuestDisplayName(displayName);
}

/** Persist display name for this browser session (create/join flows). */
export function saveSessionDisplayName(displayName: string): void {
	if (typeof window === 'undefined') return;
	const trimmed = displayName.trim();
	if (!trimmed) return;
	localStorage.setItem(DISPLAY_NAME_KEY, trimmed);
	localStorage.setItem(DISPLAY_NAME_EXPLICIT_KEY, '1');
}
