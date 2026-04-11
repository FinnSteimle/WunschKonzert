import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import LoadingState from './LoadingState.svelte';

describe('LoadingState', () => {
	it('renders default loading message', () => {
		render(LoadingState);
		expect(screen.getByText('Loading…')).toBeTruthy();
	});

	it('renders custom message when provided', () => {
		render(LoadingState, { message: 'Searching…' });
		expect(screen.getByText('Searching…')).toBeTruthy();
	});

	it('has role=status for accessibility', () => {
		render(LoadingState);
		expect(screen.getByRole('status')).toBeTruthy();
	});

	it('has aria-live=polite for screen readers', () => {
		render(LoadingState);
		const status = screen.getByRole('status');
		expect(status.getAttribute('aria-live')).toBe('polite');
	});
});
