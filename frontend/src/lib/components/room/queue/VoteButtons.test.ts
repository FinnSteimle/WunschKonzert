import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import VoteButtons from './VoteButtons.svelte';

const defaultProps = {
	upvotes: 0,
	downvotes: 0
};

describe('VoteButtons', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders upvote and downvote buttons', () => {
		render(VoteButtons, { ...defaultProps, state: 'neutral' });
		expect(screen.getByRole('button', { name: 'Upvote' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Downvote' })).toBeTruthy();
	});

	it('marks upvote button as pressed when state is upvote', () => {
		render(VoteButtons, { ...defaultProps, state: 'upvote' });
		expect(screen.getByRole('button', { name: 'Upvote' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(screen.getByRole('button', { name: 'Downvote' }).getAttribute('aria-pressed')).toBe(
			'false'
		);
	});

	it('marks downvote button as pressed when state is downvote', () => {
		render(VoteButtons, { ...defaultProps, state: 'downvote' });
		expect(screen.getByRole('button', { name: 'Upvote' }).getAttribute('aria-pressed')).toBe(
			'false'
		);
		expect(screen.getByRole('button', { name: 'Downvote' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
	});

	it('calls onVote with upvote when clicking upvote from neutral', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'neutral', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));

		expect(onVote).toHaveBeenCalledWith('upvote');
	});

	it('calls onVote with neutral when clicking upvote from upvote (toggle off)', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'upvote', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));

		expect(onVote).toHaveBeenCalledWith('neutral');
	});

	it('calls onVote with downvote when clicking downvote from neutral', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'neutral', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).toHaveBeenCalledWith('downvote');
	});

	it('calls onVote with neutral when clicking downvote from downvote (toggle off)', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'downvote', onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).toHaveBeenCalledWith('neutral');
	});

	it('does not call onVote when disabled', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'neutral', disabled: true, onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).not.toHaveBeenCalled();
	});

	it('does not call onVote when busy', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'neutral', busy: true, onVote });

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Downvote' }));

		expect(onVote).not.toHaveBeenCalled();
	});

	it('disables buttons when disabled prop is set', () => {
		render(VoteButtons, { ...defaultProps, state: 'neutral', disabled: true });
		expect((screen.getByRole('button', { name: 'Upvote' }) as HTMLButtonElement).disabled).toBe(
			true
		);
		expect((screen.getByRole('button', { name: 'Downvote' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});

	it('disables buttons when busy prop is set', () => {
		render(VoteButtons, { ...defaultProps, state: 'neutral', busy: true });
		expect((screen.getByRole('button', { name: 'Upvote' }) as HTMLButtonElement).disabled).toBe(
			true
		);
		expect((screen.getByRole('button', { name: 'Downvote' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});

	it('runs keyboard handler on upvote (Enter / Space)', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'neutral', onVote });

		const up = screen.getByRole('button', { name: 'Upvote' });
		await fireEvent.keyDown(up, { key: 'Enter' });
		await fireEvent.keyDown(up, { key: ' ' });
		await fireEvent.click(up);
		expect(onVote).toHaveBeenCalledWith('upvote');
	});

	it('runs keyboard handler on downvote', async () => {
		const onVote = vi.fn();
		render(VoteButtons, { ...defaultProps, state: 'neutral', onVote });

		const down = screen.getByRole('button', { name: 'Downvote' });
		await fireEvent.pointerDown(down);
		await fireEvent.keyDown(down, { key: ' ' });
		await fireEvent.click(down);
		expect(onVote).toHaveBeenCalledWith('downvote');
	});
});
