import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	test: {
		globals: true,
		environment: 'jsdom',
		root: 'src',
		include: ['**/*.{test,spec}.{ts,js}'],
		setupFiles: [],
		server: {
			deps: {
				inline: [/^(?!.*node_modules).*$/, 'html-encoding-sniffer', '@exodus/bytes']
			}
		}
	}
});
