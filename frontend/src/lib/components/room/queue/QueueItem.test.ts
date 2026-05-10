import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { QueueEntryDto } from '$lib/types/api';
import QueueItem from './QueueItem.svelte';

function makeEntry(overrides: Partial<QueueEntryDto> = {}): QueueEntryDto {
	return {
		queueEntryId: 'q1',
		track: {
			trackId: 't1',
			providerTrackId: 'spotify:t1',
			title: 'Song',
			artist: 'Artist',
			album: 'Album',
			duration: 200_000,
			coverUrl: 'https://example.com/cover.jpg',
			deepLink: ''
		},
		addedBy: { userId: 'user-1', displayName: 'Alice' },
		queuedAt: '2025-01-01T00:00:00Z',
		position: 0,
		status: 'queued',
		voteScore: 0,
		orderRank: 0,
		feedback: [],
		...overrides
	};
}

describe('QueueItem', () => {
	it('calls onRemove for direct-remove user (adder/host)', async () => {
		const onRemove = vi.fn();
		const onVote = vi.fn();
		render(QueueItem, {
			entry: makeEntry(),
			personalVote: 'neutral',
			voteBusyId: null,
			currentUserId: 'user-1',
			hostId: 'host-1',
			totalMembers: 3,
			onRemove,
			onVote
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Remove track' }));

		expect(onRemove).toHaveBeenCalledWith('q1');
		expect(onVote).not.toHaveBeenCalled();
	});

	it('calls onRemove to cast first skip vote for non-direct user', async () => {
		const onRemove = vi.fn();
		const onVote = vi.fn();
		render(QueueItem, {
			entry: makeEntry({ addedBy: { userId: 'other-user', displayName: 'Bob' } }),
			personalVote: 'neutral',
			voteBusyId: null,
			currentUserId: 'user-1',
			hostId: 'host-1',
			totalMembers: 3,
			onRemove,
			onVote
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Vote to remove track' }));

		expect(onRemove).toHaveBeenCalledWith('q1');
		expect(onVote).not.toHaveBeenCalled();
	});

	it('rescinds skip vote when non-direct user already voted', async () => {
		const onRemove = vi.fn();
		const onVote = vi.fn();
		render(QueueItem, {
			entry: makeEntry({
				addedBy: { userId: 'other-user', displayName: 'Bob' },
				feedback: [{ userId: 'user-1', type: 'skip', votedAt: '2025-01-01T00:00:00Z' }]
			}),
			personalVote: 'neutral',
			voteBusyId: null,
			currentUserId: 'user-1',
			hostId: 'host-1',
			totalMembers: 3,
			onRemove,
			onVote
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Vote to remove track (1 of 2)' }));

		expect(onVote).toHaveBeenCalledWith('q1', 'skip');
		expect(onRemove).not.toHaveBeenCalled();
	});

	it('disables remove button when queue entry is busy', () => {
		render(QueueItem, {
			entry: makeEntry(),
			personalVote: 'neutral',
			voteBusyId: 'q1',
			currentUserId: 'user-1',
			hostId: 'host-1',
			totalMembers: 3
		});

		const button = screen.getByRole('button', { name: 'Remove track' }) as HTMLButtonElement;
		expect(button.disabled).toBe(true);
	});

	it('renders placeholder when track has no cover art', () => {
		render(QueueItem, {
			entry: makeEntry({ track: { ...makeEntry().track, coverUrl: '' } }),
			personalVote: 'neutral',
			voteBusyId: null,
			currentUserId: 'user-1',
			hostId: 'host-1',
			totalMembers: 3
		});

		expect(screen.getByText('No art')).toBeTruthy();
	});

	it('shows score and status badges', () => {
		render(QueueItem, {
			entry: makeEntry({ voteScore: 7, status: 'queued' }),
			personalVote: 'neutral',
			voteBusyId: null,
			currentUserId: 'user-1',
			hostId: 'host-1',
			totalMembers: 3
		});

		expect(screen.getByText('Score 7')).toBeTruthy();
		expect(screen.getByText('queued')).toBeTruthy();
	});
});
