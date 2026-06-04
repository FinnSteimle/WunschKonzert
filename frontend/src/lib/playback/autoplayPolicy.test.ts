import { describe, expect, it } from 'vitest';
import { isAutoplayBlockedError } from './autoplayPolicy';

describe('isAutoplayBlockedError', () => {
	it('detects NotAllowedError', () => {
		const err = new Error('blocked');
		err.name = 'NotAllowedError';
		expect(isAutoplayBlockedError(err)).toBe(true);
	});

	it('detects interact-with-document message', () => {
		expect(
			isAutoplayBlockedError(
				new Error("play() failed because the user didn't interact with the document first.")
			)
		).toBe(true);
	});

	it('returns false for other errors', () => {
		expect(isAutoplayBlockedError(new Error('network'))).toBe(false);
	});
});
