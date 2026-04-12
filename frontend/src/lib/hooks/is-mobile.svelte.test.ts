import { describe, expect, it, vi } from 'vitest';

vi.mock('svelte/reactivity', () => {
	class MediaQueryStub {
		readonly query: string;
		constructor(query: string) {
			this.query = query;
		}
	}
	return { MediaQuery: MediaQueryStub };
});

import { IsMobile } from './is-mobile.svelte';

describe('IsMobile', () => {
	it('creates a media query with default breakpoint (767px)', () => {
		const instance = new IsMobile();
		expect((instance as unknown as { query: string }).query).toBe('max-width: 767px');
	});

	it('creates a media query with a custom breakpoint', () => {
		const instance = new IsMobile(1024);
		expect((instance as unknown as { query: string }).query).toBe('max-width: 1023px');
	});

	it('uses breakpoint minus one in the query', () => {
		const instance = new IsMobile(480);
		expect((instance as unknown as { query: string }).query).toBe('max-width: 479px');
	});
});
