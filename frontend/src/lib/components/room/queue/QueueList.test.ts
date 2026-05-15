import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { vi } from 'vitest';
import QueueList from './QueueList.svelte';
import type { QueueEntryDto } from '$lib/types/api';

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

describe('QueueList', () => {
	it('shows empty state when entries array is empty', () => {
		render(QueueList, {
			entries: [],
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 1,
			voteBusyId: null
		});
		expect(screen.getByText('Queue is empty')).toBeTruthy();
		expect(screen.getByText('Search for a song and add it to the queue.')).toBeTruthy();
	});

	it('shows empty state when all entries are played', () => {
		const entries = [
			makeEntry({ queueEntryId: 'q1', status: 'played' }),
			makeEntry({ queueEntryId: 'q2', status: 'played', position: 1 })
		];

		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 2,
			voteBusyId: null
		});

		expect(screen.getByText('Queue is empty')).toBeTruthy();
		expect(screen.queryByRole('list', { name: 'Playback queue' })).toBeNull();
	});

	it('renders queue entries', () => {
		const entries = [
			makeEntry({ queueEntryId: 'q1', track: { ...makeEntry().track, title: 'Song A' } }),
			makeEntry({ queueEntryId: 'q2', track: { ...makeEntry().track, title: 'Song B' } })
		];
		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 2,
			voteBusyId: null
		});

		expect(screen.getByText('Song A')).toBeTruthy();
		expect(screen.getByText('Song B')).toBeTruthy();
	});

	it('sorts unplayed entries by vote score descending', () => {
		const entries = [
			makeEntry({
				queueEntryId: 'q1',
				track: { ...makeEntry().track, title: 'Low Score' },
				voteScore: 1,
				position: 0,
				status: 'queued'
			}),
			makeEntry({
				queueEntryId: 'q2',
				track: { ...makeEntry().track, title: 'High Score' },
				voteScore: 10,
				position: 1,
				status: 'queued'
			})
		];
		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 2,
			voteBusyId: null
		});

		const items = screen.getAllByRole('listitem');
		expect(items[0].textContent).toContain('High Score');
		expect(items[1].textContent).toContain('Low Score');
	});

	it('hides played songs and only renders unplayed entries', () => {
		const entries = [
			makeEntry({
				queueEntryId: 'q1',
				track: { ...makeEntry().track, title: 'Played Second' },
				status: 'played',
				position: 2,
				voteScore: 100
			}),
			makeEntry({
				queueEntryId: 'q2',
				track: { ...makeEntry().track, title: 'Played First' },
				status: 'played',
				position: 1,
				voteScore: 0
			}),
			makeEntry({
				queueEntryId: 'q3',
				track: { ...makeEntry().track, title: 'Unplayed High Vote' },
				status: 'queued',
				position: 3,
				voteScore: 50
			})
		];
		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 3,
			voteBusyId: null
		});

		const items = screen.getAllByRole('listitem');
		expect(items).toHaveLength(1);
		expect(items[0].textContent).toContain('Unplayed High Vote');
		expect(screen.queryByText('Played First')).toBeNull();
		expect(screen.queryByText('Played Second')).toBeNull();
	});

	it('tie-breaks by position ascending', () => {
		const entries = [
			makeEntry({
				queueEntryId: 'q1',
				track: { ...makeEntry().track, title: 'Second' },
				voteScore: 5,
				position: 2
			}),
			makeEntry({
				queueEntryId: 'q2',
				track: { ...makeEntry().track, title: 'First' },
				voteScore: 5,
				position: 1
			})
		];
		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 2,
			voteBusyId: null
		});

		const items = screen.getAllByRole('listitem');
		expect(items[0].textContent).toContain('First');
		expect(items[1].textContent).toContain('Second');
	});

	it('has accessible list with correct aria-label', () => {
		const entries = [makeEntry()];
		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 1,
			voteBusyId: null
		});

		expect(screen.getByRole('list', { name: 'Playback queue' })).toBeTruthy();
	});

	it('forwards vote and remove callbacks to queue item actions', async () => {
		const onVote = vi.fn();
		const onRemove = vi.fn();
		const entries = [makeEntry()];

		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 2,
			voteBusyId: null,
			onVote,
			onRemove
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Upvote' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Remove track' }));

		expect(onVote).toHaveBeenCalledWith('q1', 'upvote');
		expect(onRemove).toHaveBeenCalledWith('q1');
	});

	it('disables actions for busy queue entry only', () => {
		const entries = [
			makeEntry({ queueEntryId: 'q1' }),
			makeEntry({
				queueEntryId: 'q2',
				position: 1,
				track: { ...makeEntry().track, title: 'Second song' }
			})
		];

		render(QueueList, {
			entries,
			userId: 'user-1',
			hostId: 'host-1',
			totalMembers: 2,
			voteBusyId: 'q1'
		});

		const removeButtons = screen.getAllByRole('button', {
			name: 'Remove track'
		}) as HTMLButtonElement[];
		const upvoteButtons = screen.getAllByRole('button', { name: 'Upvote' }) as HTMLButtonElement[];

		expect(removeButtons[0].disabled).toBe(true);
		expect(upvoteButtons[0].disabled).toBe(true);
		expect(removeButtons[1].disabled).toBe(false);
		expect(upvoteButtons[1].disabled).toBe(false);
	});
});
