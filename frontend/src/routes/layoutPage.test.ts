import { screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from 'svelte';
import LayoutPage from './+layout.svelte';

vi.mock('mode-watcher', () => ({
	ModeWatcher: function ModeWatcherStub() {},
	toggleMode: vi.fn()
}));

vi.mock('$lib/components/ui/sonner', () => ({
	Toaster: function ToasterStub() {}
}));

describe('+layout.svelte', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the ThemeToggle button', () => {
		const target = document.body.appendChild(document.createElement('div'));
		mount(LayoutPage, {
			target,
			props: {
				children: (() => {}) as never
			}
		});

		expect(screen.getByRole('button', { name: 'Toggle theme' })).toBeTruthy();
		target.remove();
	});

	it('renders child content via snippet', () => {
		const target = document.body.appendChild(document.createElement('div'));
		mount(LayoutPage, {
			target,
			props: {
				children: ((anchor: Node) => {
					const el = document.createElement('span');
					el.textContent = 'child-sentinel';
					anchor.parentNode?.insertBefore(el, anchor);
				}) as never
			}
		});

		expect(screen.getByText('child-sentinel')).toBeTruthy();
		target.remove();
	});
});
