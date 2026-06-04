/** Crockford-style room codes (no I, O, 0, 1), case-insensitive in URLs. */
const JOIN_CODE_RE = /^[A-HJ-NP-Z2-9]{6}$/i;

export type ParsedRoomSlug = { kind: 'joinCode'; joinCode: string } | { kind: 'invalid' };

export function parseRoomSlug(raw: string): ParsedRoomSlug {
	const segment = raw.trim();
	const code = segment.replace(/\s/g, '').toUpperCase();
	if (JOIN_CODE_RE.test(code)) {
		return { kind: 'joinCode', joinCode: code };
	}
	return { kind: 'invalid' };
}
