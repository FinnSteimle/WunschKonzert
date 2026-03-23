import { describe, it, expect } from 'vitest';

describe('Smoke Test', () => {
	it('should verify that math still works', () => {
		expect(1 + 1).toBe(2);
	});

	it('should verify environment variables (Vite-style)', () => {
		// This just checks if the test environment is correctly set up
		expect(import.meta.env.MODE).toBeDefined();
	});
});
