import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	ssr: {
		noExternal: ['html-encoding-sniffer', '@exodus/bytes', 'jsdom']
	},
	test: {
		globals: true,
		environment: 'jsdom',
		include: ['src/**/*.{test,spec}.{ts,js}'],
		setupFiles: [],
		server: {
			deps: {
				inline: ['html-encoding-sniffer', '@exodus/bytes', 'jsdom']
			}
		},
		coverage: {
			provider: 'v8',
			reporter: ['text', 'cobertura'],
			include: ['src/**/*.{ts}']
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
