import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import CurrentSongCard from './CurrentSongCard.svelte';
import type { QueueEntryDto } from '$lib/types/api';

function makeEntry(overrides: Partial<QueueEntryDto> = {}): QueueEntryDto {
	return {
		queueEntryId: 'q1',
		track: {
			trackId: 't1',
			providerTrackId: 'spotify:t1',
			title: 'Test Song',
			artist: 'Test Artist',
			album: 'Test Album',
			duration: 200_000,
			coverUrl: 'https://example.com/cover.jpg',
			deepLink: 'https://example.com/track/t1'
		},
		addedBy: { userId: 'user-1', displayName: 'Alice' },
		queuedAt: '2025-01-01T00:00:00Z',
		position: 0,
		status: 'playing',
		voteScore: 5,
		orderRank: 0,
		feedback: [],
		...overrides
	};
}

describe('CurrentSongCard', () => {
	it('shows empty state when entry is null', () => {
		render(CurrentSongCard, { entry: null });
		expect(screen.getByText('Nothing playing')).toBeTruthy();
		expect(screen.getByText('Add a song to the queue to get started.')).toBeTruthy();
	});

	it('displays the track title, artist, and album', () => {
		render(CurrentSongCard, { entry: makeEntry() });
		expect(screen.getByText('Test Song')).toBeTruthy();
		expect(screen.getByText(/Test Artist/)).toBeTruthy();
		expect(screen.getByText(/Test Album/)).toBeTruthy();
	});

	it('shows Now playing badge', () => {
		render(CurrentSongCard, { entry: makeEntry() });
		expect(screen.getByText('Now playing')).toBeTruthy();
	});

	it('shows the display name of who added the song', () => {
		render(CurrentSongCard, { entry: makeEntry() });
		expect(screen.getByText('Added by Alice')).toBeTruthy();
	});

	it('renders cover art when coverUrl is present', () => {
		const { container } = render(CurrentSongCard, { entry: makeEntry() });
		const img = container.querySelector('img');
		expect(img).not.toBeNull();
		expect(img!.getAttribute('src')).toBe('https://example.com/cover.jpg');
	});

	it('shows placeholder when coverUrl is empty', () => {
		render(CurrentSongCard, { entry: makeEntry({ track: { ...makeEntry().track, coverUrl: '' } }) });
		expect(screen.getByText('No art')).toBeTruthy();
	});

	it('renders Open track link when deepLink is present', () => {
		render(CurrentSongCard, { entry: makeEntry() });
		const link = screen.getByRole('link', { name: 'Open track' });
		expect(link.getAttribute('href')).toBe('https://example.com/track/t1');
		expect(link.getAttribute('target')).toBe('_blank');
	});

	it('does not render Open track link when deepLink is empty', () => {
		render(CurrentSongCard, {
			entry: makeEntry({ track: { ...makeEntry().track, deepLink: '' } })
		});
		expect(screen.queryByRole('link', { name: 'Open track' })).toBeNull();
	});

	it('shows entry status when present', () => {
		render(CurrentSongCard, { entry: makeEntry({ status: 'playing' }) });
		expect(screen.getByText('playing')).toBeTruthy();
	});
});
