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
		server: {
			deps: {
				inline: ['html-encoding-sniffer', '@exodus/bytes', 'jsdom']
			}
		},
		coverage: {
			provider: 'v8',
			reporter: ['text', 'text-summary', 'cobertura'],
			include: ['src/**/*.ts'],
			exclude: ['src/lib/components/ui/*'],
			clean: false
			/*
			thresholds: {
				lines: 80,
				functions: 80,
				branches: 80,
				statements: 80
			}
			*/
		}
	}
});
