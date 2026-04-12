import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
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
		render(QueueList, { entries: [], userId: 'user-1', voteBusyId: null });
		expect(screen.getByText('Queue is empty')).toBeTruthy();
		expect(screen.getByText('Search for a song and add it to the queue.')).toBeTruthy();
	});

	it('renders queue entries', () => {
		const entries = [
			makeEntry({ queueEntryId: 'q1', track: { ...makeEntry().track, title: 'Song A' } }),
			makeEntry({ queueEntryId: 'q2', track: { ...makeEntry().track, title: 'Song B' } })
		];
		render(QueueList, { entries, userId: 'user-1', voteBusyId: null });

		expect(screen.getByText('Song A')).toBeTruthy();
		expect(screen.getByText('Song B')).toBeTruthy();
	});

	it('sorts entries by vote score descending', () => {
		const entries = [
			makeEntry({
				queueEntryId: 'q1',
				track: { ...makeEntry().track, title: 'Low Score' },
				voteScore: 1,
				position: 0
			}),
			makeEntry({
				queueEntryId: 'q2',
				track: { ...makeEntry().track, title: 'High Score' },
				voteScore: 10,
				position: 1
			})
		];
		render(QueueList, { entries, userId: 'user-1', voteBusyId: null });

		const items = screen.getAllByRole('listitem');
		expect(items[0].textContent).toContain('High Score');
		expect(items[1].textContent).toContain('Low Score');
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
		render(QueueList, { entries, userId: 'user-1', voteBusyId: null });

		const items = screen.getAllByRole('listitem');
		expect(items[0].textContent).toContain('First');
		expect(items[1].textContent).toContain('Second');
	});

	it('has accessible list with correct aria-label', () => {
		const entries = [makeEntry()];
		render(QueueList, { entries, userId: 'user-1', voteBusyId: null });

		expect(screen.getByRole('list', { name: 'Playback queue' })).toBeTruthy();
	});
});
