import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

const isVitest =
	typeof globalThis !== 'undefined' &&
	'process' in globalThis &&
	!!(globalThis as { process?: { env?: { VITEST?: string } } }).process?.env?.VITEST;

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	...(isVitest
		? {
				resolve: {
					conditions: ['browser', 'development', 'import', 'module', 'default']
				}
			}
		: {}),
	ssr: {
		noExternal: ['html-encoding-sniffer', '@exodus/bytes', 'jsdom']
	},
	test: {
		globals: true,
		environment: 'jsdom',
		include: ['src/**/*.{test,spec}.{ts,js}'],
		setupFiles: ['src/test/setup.ts'],
		env: {
			PUBLIC_API_URL: 'http://localhost:8000',
			PUBLIC_WS_URL: 'ws://localhost:8000'
		},
		server: {
			deps: {
				inline: ['html-encoding-sniffer', '@exodus/bytes', 'jsdom']
			}
		},
		coverage: {
			provider: 'v8',
			reporter: ['text', 'text-summary', 'cobertura'],
			include: ['src/**/*.ts', 'src/**/*.svelte'],
			exclude: [
				'src/lib/components/ui/*',
				// Spotify Web Playback SDK glue — DOM script injection + globals; smoke-tested manually.
				'src/lib/playback/**',
				// Interfaces only; no runnable lines.
				'src/lib/types/**',
				'**/*.d.ts',
				'src/lib/index.ts'
			],
			clean: true,
			thresholds: {
				lines: 80,
				statements: 80
			}
		}
	}
});
