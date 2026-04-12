import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getOrCreateSessionUser, saveSessionDisplayName } from './userSession';

describe('getOrCreateSessionUser', () => {
	beforeEach(() => {
		localStorage.clear();
	});

	it('creates and persists a user id when missing', () => {
		const randomSpy = vi.spyOn(Math, 'random').mockReturnValue(0);

		const first = getOrCreateSessionUser();
		const second = getOrCreateSessionUser();

		expect(first.userId).toBe('U_AAAAAAAAAA');
		expect(first.displayName).toBe('');
		expect(second.userId).toBe('U_AAAAAAAAAA');
		expect(localStorage.getItem('wk_user_id')).toBe('U_AAAAAAAAAA');

		randomSpy.mockRestore();
	});

	it('reuses persisted user id and display name', () => {
		localStorage.setItem('wk_user_id', 'U_ZYXWVUTSRQ');
		localStorage.setItem('wk_display_name', 'Alice');

		expect(getOrCreateSessionUser()).toEqual({
			userId: 'U_ZYXWVUTSRQ',
			displayName: 'Alice'
		});
	});
});

describe('saveSessionDisplayName', () => {
	beforeEach(() => {
		localStorage.clear();
	});

	it('saves trimmed non-empty values only', () => {
		saveSessionDisplayName('  Alice  ');
		expect(localStorage.getItem('wk_display_name')).toBe('Alice');

		saveSessionDisplayName('   ');
		expect(localStorage.getItem('wk_display_name')).toBe('Alice');
	});
});
