/** Crockford-style room codes (no I, O, 0, 1), case-insensitive in URLs. */
const JOIN_CODE_RE = /^[A-HJ-NP-Z2-9]{6}$/i;

const ROOM_UUID_RE =
	/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type ParsedRoomSlug =
	| { kind: 'roomId'; roomId: string }
	| { kind: 'joinCode'; joinCode: string }
	| { kind: 'invalid' };

export function parseRoomSlug(raw: string): ParsedRoomSlug {
	const segment = raw.trim();
	if (ROOM_UUID_RE.test(segment)) {
		return { kind: 'roomId', roomId: segment };
	}
	const code = segment.replace(/\s/g, '').toUpperCase();
	if (JOIN_CODE_RE.test(code)) {
		return { kind: 'joinCode', joinCode: code };
	}
	return { kind: 'invalid' };
}
