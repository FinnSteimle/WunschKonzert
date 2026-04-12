import { describe, expect, it } from 'vitest';
import { load } from './+page';

describe('join/[code] load', () => {
	it('redirects to room route using provided code', () => {
		try {
			load({ params: { code: 'ab2cd3' } } as never);
			throw new Error('expected redirect');
		} catch (err) {
			const redirect = err as { status?: number; location?: string };
			expect(redirect.status).toBe(307);
			expect(redirect.location).toBe('/room/ab2cd3');
		}
	});
});
