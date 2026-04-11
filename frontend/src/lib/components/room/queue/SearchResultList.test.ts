import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SearchResultList from './SearchResultList.svelte';
import type { TrackDto } from '$lib/types/api';

function makeTrack(id: string, title: string): TrackDto {
	return {
		trackId: id,
		providerTrackId: `spotify:${id}`,
		title,
		artist: 'Artist',
		album: 'Album',
		duration: 200_000,
		coverUrl: 'https://example.com/cover.jpg',
		deepLink: ''
	};
}

describe('SearchResultList', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows empty state when tracks array is empty', () => {
		render(SearchResultList, { tracks: [], addingTrackId: null });
		expect(screen.getByText('No results')).toBeTruthy();
		expect(screen.getByText('Try another search.')).toBeTruthy();
	});

	it('renders track titles and artists', () => {
		const tracks = [makeTrack('t1', 'Song A'), makeTrack('t2', 'Song B')];
		render(SearchResultList, { tracks, addingTrackId: null });

		expect(screen.getByText('Song A')).toBeTruthy();
		expect(screen.getByText('Song B')).toBeTruthy();
	});

	it('renders cover art for tracks with coverUrl', () => {
		const tracks = [makeTrack('t1', 'Song A')];
		const { container } = render(SearchResultList, { tracks, addingTrackId: null });

		const images = container.querySelectorAll('img');
		expect(images.length).toBeGreaterThanOrEqual(1);
		expect(images[0].getAttribute('src')).toBe('https://example.com/cover.jpg');
	});

	it('shows No art placeholder when coverUrl is empty', () => {
		const track = { ...makeTrack('t1', 'Song A'), coverUrl: '' };
		render(SearchResultList, { tracks: [track], addingTrackId: null });

		expect(screen.getByText('No art')).toBeTruthy();
	});

	it('calls onAdd when add button is clicked', async () => {
		const onAdd = vi.fn();
		const tracks = [makeTrack('t1', 'Song A')];
		render(SearchResultList, { tracks, addingTrackId: null, onAdd });

		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue' }));

		expect(onAdd).toHaveBeenCalledWith(tracks[0]);
	});

	it('disables add button for track being added', () => {
		const tracks = [makeTrack('t1', 'Song A')];
		render(SearchResultList, { tracks, addingTrackId: 't1' });

		const btn = screen.getByRole('button', { name: 'Add to queue' }) as HTMLButtonElement;
		expect(btn.disabled).toBe(true);
	});

	it('shows Adding… text for track being added', () => {
		const tracks = [makeTrack('t1', 'Song A')];
		render(SearchResultList, { tracks, addingTrackId: 't1' });

		expect(screen.getByText('Adding…')).toBeTruthy();
	});

	it('shows In queue badge and disables button for queued tracks', () => {
		const tracks = [makeTrack('t1', 'Song A')];
		const queuedTrackIds = new Set(['t1']);
		render(SearchResultList, { tracks, addingTrackId: null, queuedTrackIds });

		expect(screen.getByText('In queue')).toBeTruthy();
		const btn = screen.getByRole('button', { name: 'Already in queue' }) as HTMLButtonElement;
		expect(btn.disabled).toBe(true);
	});

	it('has a search results list with correct aria-label', () => {
		const tracks = [makeTrack('t1', 'Song A')];
		render(SearchResultList, { tracks, addingTrackId: null });

		expect(screen.getByRole('list', { name: 'Search results' })).toBeTruthy();
	});
});
