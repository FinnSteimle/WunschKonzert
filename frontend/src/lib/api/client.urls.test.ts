import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('getApiBaseUrl / getWsBaseUrl', () => {
	beforeEach(() => {
		vi.resetModules();
	});

	afterEach(() => {
		vi.unstubAllEnvs();
		vi.unstubAllGlobals();
	});

	it('PUBLIC_API_URL and PUBLIC_WS_URL trimmed; trailing slashes stripped', async () => {
		vi.stubEnv('PUBLIC_API_URL', '  https://api.example.test/ ');
		vi.stubEnv('PUBLIC_WS_URL', '  wss://ws.example.test/ ');
		const { getApiBaseUrl, getWsBaseUrl } = await import('./client');

		expect(getApiBaseUrl()).toBe('https://api.example.test');
		expect(getWsBaseUrl()).toBe('wss://ws.example.test');
	});

	it('falls back when window has no location (SSR-style)', async () => {
		vi.stubEnv('PUBLIC_API_URL', '');
		vi.stubEnv('PUBLIC_WS_URL', '');
		vi.stubGlobal('window', {} as Window & typeof globalThis);
		const { getApiBaseUrl, getWsBaseUrl } = await import('./client');

		expect(getApiBaseUrl()).toBe('http://localhost:8000');
		expect(getWsBaseUrl()).toBe('ws://localhost:8000');
	});

	it('with https origin uses same-host /api and wss /api path', async () => {
		vi.stubEnv('PUBLIC_API_URL', '');
		vi.stubEnv('PUBLIC_WS_URL', '');
		vi.stubGlobal('window', {
			location: {
				origin: 'https://example.com',
				host: 'example.com',
				protocol: 'https:',
				hostname: 'example.com',
				port: ''
			}
		});
		const { getApiBaseUrl, getWsBaseUrl } = await import('./client');

		expect(getApiBaseUrl()).toBe('https://example.com/api');
		expect(getWsBaseUrl()).toBe('wss://example.com/api');
	});

	it('localhost vite port uses direct 127.0.0.1:8000 and ws', async () => {
		vi.stubEnv('PUBLIC_API_URL', '');
		vi.stubEnv('PUBLIC_WS_URL', '');
		vi.stubGlobal('window', {
			location: {
				origin: 'http://localhost:5173',
				host: 'localhost:5173',
				protocol: 'http:',
				hostname: 'localhost',
				port: '5173'
			}
		});
		const { getApiBaseUrl, getWsBaseUrl } = await import('./client');

		expect(getApiBaseUrl()).toBe('http://127.0.0.1:8000');
		expect(getWsBaseUrl()).toBe('ws://127.0.0.1:8000');
	});

	it('PUBLIC_WS_URL empty string yields env branch before window for ws helper', async () => {
		vi.stubEnv('PUBLIC_WS_URL', 'ws://explicit-ws.example');
		vi.stubGlobal('window', {
			location: {
				origin: 'https://example.com',
				host: 'example.com',
				protocol: 'https:',
				hostname: 'example.com',
				port: ''
			}
		});
		const { getWsBaseUrl } = await import('./client');
		expect(getWsBaseUrl()).toBe('ws://explicit-ws.example');
	});
});
