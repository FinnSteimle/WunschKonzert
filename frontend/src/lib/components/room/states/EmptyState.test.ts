import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import EmptyState from './EmptyState.svelte';

describe('EmptyState', () => {
	it('renders title', () => {
		render(EmptyState, { title: 'No items' });
		expect(screen.getByText('No items')).toBeTruthy();
	});

	it('renders description when provided', () => {
		render(EmptyState, { title: 'Empty', description: 'Nothing to show here.' });
		expect(screen.getByText('Nothing to show here.')).toBeTruthy();
	});

	it('does not render description when not provided', () => {
		const { container } = render(EmptyState, { title: 'Empty' });
		const paragraphs = container.querySelectorAll('p');
		expect(paragraphs).toHaveLength(1);
	});

	it('has role=status for accessibility', () => {
		render(EmptyState, { title: 'Empty' });
		expect(screen.getByRole('status')).toBeTruthy();
	});
});
