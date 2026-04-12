import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import VoteButtons from './VoteButtons.svelte';

describe('VoteButtons', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders upvote and downvote buttons', () => {
		render(VoteButtons, { state: 'neutral' });
		expect(screen.getByRole('button', { name: 'Upvote' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Downvote' })).toBeTruthy();
	});

	it('marks upvote button as pressed when state is upvote', () => {
		render(VoteButtons, { state: 'upvote' });
		expect(screen.getByRole('button', { name: 'Upvote' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: 'Downvote' }).getAttribute('aria-pressed')).toBe(
			'false'
		);
	});

	it('marks downvote button as pressed when state is downvote', () => {
		render(VoteButtons, { state: 'downvote' });
		expect(screen.getByRole('button', { name: 'Upvote' }).getAttribute('aria-pressed')).toBe(
			'false'
		);
		expect(screen.getByRole('button', { name: 'Downvote' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('calls onVote with upvote when clicking upvote from neutral', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { state: 'neutral', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));

		expect(onVote).toHaveBeenCalledWith('upvote');
	});

	it('calls onVote with neutral when clicking upvote from upvote (toggle off)', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { state: 'upvote', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));

		expect(onVote).toHaveBeenCalledWith('neutral');
	});

	it('calls onVote with downvote when clicking downvote from neutral', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { state: 'neutral', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).toHaveBeenCalledWith('downvote');
	});

	it('calls onVote with neutral when clicking downvote from downvote (toggle off)', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { state: 'downvote', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).toHaveBeenCalledWith('neutral');
	});

	it('does not call onVote when disabled', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { state: 'neutral', disabled: true, onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).not.toHaveBeenCalled();
	});

	it('does not call onVote when busy', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { state: 'neutral', busy: true, onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).not.toHaveBeenCalled();
	});

	it('disables buttons when disabled prop is set', () => {
		render(VoteButtons, { state: 'neutral', disabled: true });
		expect(
			(screen.getByRole('button', { name: 'Upvote' }) as HTMLButtonElement).disabled
		).toBe(true);
		expect(
			(screen.getByRole('button', { name: 'Downvote' }) as HTMLButtonElement).disabled
		).toBe(true);
	});

	it('disables buttons when busy prop is set', () => {
		render(VoteButtons, { state: 'neutral', busy: true });
		expect(
			(screen.getByRole('button', { name: 'Upvote' }) as HTMLButtonElement).disabled
		).toBe(true);
		expect(
			(screen.getByRole('button', { name: 'Downvote' }) as HTMLButtonElement).disabled
		).toBe(true);
	});
});
