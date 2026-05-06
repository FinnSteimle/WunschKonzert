import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ReplayVotePanel from './ReplayVotePanel.svelte';
import type { ReplayVoteStateDto, TrackDto } from '$lib/types/api';

const track: TrackDto = {
	trackId: 't-prev',
	providerTrackId: 'spotify:t-prev',
	title: 'Previous Hit',
	artist: 'The Band',
	album: 'Album',
	duration: 180,
	coverUrl: '',
	deepLink: ''
};

function makeReplayVote(overrides: Partial<ReplayVoteStateDto> = {}): ReplayVoteStateDto {
	return {
		targetQueueEntryId: 'q-prev',
		track,
		voteCount: 1,
		voterUserIds: ['U_USER1'],
		activeUserCount: 3,
		closesAt: new Date(Date.now() + 120_000).toISOString(),
		status: 'open',
		...overrides
	};
}

describe('ReplayVotePanel', () => {
	it('shows vote totals and vote controls when open', () => {
		const onVote = vi.fn();
		const onRetract = vi.fn();
		render(ReplayVotePanel, {
			props: {
				replayVote: makeReplayVote({ voteCount: 1, voterUserIds: [], activeUserCount: 3 }),
				userId: 'U_USER1',
				connected: true,
				busy: false,
				onVote,
				onRetract
			}
		});

		expect(screen.getByText('Replay last track')).toBeTruthy();
		expect(screen.getByText(/Previous Hit/)).toBeTruthy();
		expect(screen.getByText(/1 \/ 2 for majority/)).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Vote to replay' })).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Remove vote' })).toBeNull();
	});

	it('shows your vote state and retract when the current user has voted', () => {
		const onRetract = vi.fn();
		render(ReplayVotePanel, {
			props: {
				replayVote: makeReplayVote({ voterUserIds: ['U_USER1'] }),
				userId: 'U_USER1',
				connected: true,
				busy: false,
				onVote: vi.fn(),
				onRetract
			}
		});

		expect(screen.getByText('Your vote counted')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Voted' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Remove vote' })).toBeTruthy();
	});

	it('calls onVote when voting', async () => {
		const onVote = vi.fn();
		render(ReplayVotePanel, {
			props: {
				replayVote: makeReplayVote({
					voteCount: 0,
					voterUserIds: [],
					activeUserCount: 2
				}),
				userId: 'U_USER1',
				connected: true,
				busy: false,
				onVote,
				onRetract: vi.fn()
			}
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Vote to replay' }));
		expect(onVote).toHaveBeenCalledTimes(1);
	});

	it('calls onRetract when removing a vote', async () => {
		const onRetract = vi.fn();
		render(ReplayVotePanel, {
			props: {
				replayVote: makeReplayVote({ voterUserIds: ['U_USER1'] }),
				userId: 'U_USER1',
				connected: true,
				busy: false,
				onVote: vi.fn(),
				onRetract
			}
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Remove vote' }));
		expect(onRetract).toHaveBeenCalledTimes(1);
	});

	it('shows scheduled copy when status is met', () => {
		render(ReplayVotePanel, {
			props: {
				replayVote: makeReplayVote({ status: 'met' }),
				userId: 'U_USER1',
				connected: true,
				busy: false
			}
		});

		expect(screen.getByText('Replay scheduled')).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Vote to replay' })).toBeNull();
	});
});
