import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import RemoveButton from './RemoveButton.svelte';

const baseProps = {
	canRemoveDirectly: false,
	skipCount: 0,
	requiredVotes: 3,
	hasVoted: false
};

describe('RemoveButton', () => {
	it('renders remove mode for direct removal', () => {
		render(RemoveButton, { ...baseProps, canRemoveDirectly: true });

		expect(screen.getByRole('button', { name: 'Remove track' })).toBeTruthy();
		expect(screen.getByText('Remove')).toBeTruthy();
	});

	it('shows direct remove vote counter when skip votes already exist', () => {
		render(RemoveButton, {
			...baseProps,
			canRemoveDirectly: true,
			skipCount: 2,
			requiredVotes: 5
		});

		expect(
			screen.getByRole('button', { name: 'Remove track (2 of 5 votes to skip)' })
		).toBeTruthy();
		expect(screen.getByLabelText('2 of 5 votes to skip')).toBeTruthy();
		expect(screen.getByText('2/5')).toBeTruthy();
	});

	it('renders neutral mode when voting has not started', () => {
		render(RemoveButton, { ...baseProps, skipCount: 0, canRemoveDirectly: false });

		expect(screen.getByRole('button', { name: 'Vote to remove track' })).toBeTruthy();
		expect(screen.getByText('Skip')).toBeTruthy();
	});

	it('renders voting mode and aria-pressed false when user has not voted', () => {
		render(RemoveButton, { ...baseProps, skipCount: 1, requiredVotes: 4, hasVoted: false });

		const button = screen.getByRole('button', { name: 'Vote to remove track (1 of 4)' });
		expect(button.getAttribute('aria-pressed')).toBe('false');
		expect(screen.getByLabelText('1 of 4 votes to remove')).toBeTruthy();
		expect(screen.getByText('1/4')).toBeTruthy();
	});

	it('renders voting mode and aria-pressed true when user has voted', () => {
		render(RemoveButton, { ...baseProps, skipCount: 3, requiredVotes: 4, hasVoted: true });

		const button = screen.getByRole('button', { name: 'Vote to remove track (3 of 4)' });
		expect(button.getAttribute('aria-pressed')).toBe('true');
	});

	it('calls onRemove on click when not busy', async () => {
		const onRemove = vi.fn();
		render(RemoveButton, { ...baseProps, onRemove });

		await fireEvent.click(screen.getByRole('button', { name: 'Vote to remove track' }));

		expect(onRemove).toHaveBeenCalledTimes(1);
	});

	it('does not call onRemove when busy', async () => {
		const onRemove = vi.fn();
		render(RemoveButton, { ...baseProps, busy: true, onRemove });

		const button = screen.getByRole('button', {
			name: 'Vote to remove track'
		}) as HTMLButtonElement;
		expect(button.disabled).toBe(true);

		await fireEvent.click(button);

		expect(onRemove).not.toHaveBeenCalled();
	});
});
