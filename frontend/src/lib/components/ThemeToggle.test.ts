import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ThemeToggle from './ThemeToggle.svelte';
import { toggleMode } from 'mode-watcher';

vi.mock('mode-watcher', () => ({
	toggleMode: vi.fn()
}));

describe('ThemeToggle', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders an accessible toggle button', () => {
		render(ThemeToggle);

		const button = screen.getByRole('button', { name: 'Toggle theme' });
		expect(button).toBeTruthy();
	});

	it('calls toggleMode when clicked', async () => {
		render(ThemeToggle);

		await fireEvent.click(screen.getByRole('button', { name: 'Toggle theme' }));

		expect(toggleMode).toHaveBeenCalledOnce();
	});

	it('calls toggleMode on each click', async () => {
		render(ThemeToggle);

		const button = screen.getByRole('button', { name: 'Toggle theme' });
		await fireEvent.click(button);
		await fireEvent.click(button);

		expect(toggleMode).toHaveBeenCalledTimes(2);
	});
});
