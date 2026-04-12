import { describe, expect, it } from 'vitest';
import { parseRoomSlug } from './slug';

describe('parseRoomSlug', () => {
	it('parses valid join codes case-insensitively', () => {
		expect(parseRoomSlug('ab2cd3')).toEqual({ kind: 'joinCode', joinCode: 'AB2CD3' });
	});

	it('ignores outer and inner whitespace in join codes', () => {
		expect(parseRoomSlug('  a b2 c d3  ')).toEqual({ kind: 'joinCode', joinCode: 'AB2CD3' });
	});

	it('returns invalid for disallowed characters', () => {
		expect(parseRoomSlug('AB1CD3')).toEqual({ kind: 'invalid' });
		expect(parseRoomSlug('AB0CD3')).toEqual({ kind: 'invalid' });
		expect(parseRoomSlug('ABICD3')).toEqual({ kind: 'invalid' });
		expect(parseRoomSlug('ABOCD3')).toEqual({ kind: 'invalid' });
	});

	it('returns invalid for wrong lengths', () => {
		expect(parseRoomSlug('AB2CD')).toEqual({ kind: 'invalid' });
		expect(parseRoomSlug('AB2CD34')).toEqual({ kind: 'invalid' });
	});
});
