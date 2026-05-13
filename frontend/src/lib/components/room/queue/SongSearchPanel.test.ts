import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SongSearchPanel from './SongSearchPanel.svelte';
import { apiClient } from '$lib/api/client';
import { toast } from 'svelte-sonner';
import type { TrackDto } from '$lib/types/api';

vi.mock('$lib/api/client', () => ({
	apiClient: {
		searchSongs: vi.fn()
	}
}));

vi.mock('svelte-sonner', () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
		message: vi.fn()
	}
}));

function makeTrack(overrides: Partial<TrackDto> = {}): TrackDto {
	return {
		trackId: 't1',
		providerTrackId: 'spotify:t1',
		title: 'Test Song',
		artist: 'Test Artist',
		album: 'Test Album',
		duration: 200000,
		coverUrl: 'https://example.com/cover.jpg',
		deepLink: 'https://example.com/track/t1',
		...overrides
	};
}

describe('SongSearchPanel', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the search input and button', () => {
		render(SongSearchPanel, { roomId: 'room-1' });

		expect(screen.getByLabelText('Search songs')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
	});

	it('disables search button when query is shorter than 2 chars', () => {
		render(SongSearchPanel, { roomId: 'room-1' });

		expect((screen.getByRole('button', { name: 'Search' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});

	it('enables search button when query is 2+ chars', async () => {
		render(SongSearchPanel, { roomId: 'room-1' });

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'AC' }
		});

		expect((screen.getByRole('button', { name: 'Search' }) as HTMLButtonElement).disabled).toBe(
			false
		);
	});

	it('calls searchSongs API on button click and renders results', async () => {
		const tracks = [makeTrack(), makeTrack({ trackId: 't2', title: 'Second Song' })];
		vi.mocked(apiClient.searchSongs).mockResolvedValue({
			provider: 'spotify',
			query: 'test',
			tracks
		});

		render(SongSearchPanel, { roomId: 'room-1' });

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'test' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

		await waitFor(() => expect(screen.getByText('Test Song')).toBeTruthy());
		expect(screen.getByText('Second Song')).toBeTruthy();
		expect(apiClient.searchSongs).toHaveBeenCalledWith('room-1', 'test');
	});

	it('calls searchSongs API on Enter key press', async () => {
		vi.mocked(apiClient.searchSongs).mockResolvedValue({
			provider: 'spotify',
			query: 'rock',
			tracks: [makeTrack()]
		});

		render(SongSearchPanel, { roomId: 'room-1' });

		const input = screen.getByLabelText('Search songs');
		await fireEvent.input(input, { target: { value: 'rock' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		await waitFor(() => expect(apiClient.searchSongs).toHaveBeenCalledWith('room-1', 'rock'));
	});

	it('does not search on Enter when query is too short', async () => {
		render(SongSearchPanel, { roomId: 'room-1' });

		const input = screen.getByLabelText('Search songs');
		await fireEvent.input(input, { target: { value: 'a' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		expect(apiClient.searchSongs).not.toHaveBeenCalled();
	});

	it('shows error state when search fails', async () => {
		vi.mocked(apiClient.searchSongs).mockRejectedValue(new Error('Network error'));

		render(SongSearchPanel, { roomId: 'room-1' });

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'test' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

		await waitFor(() => expect(screen.getByText('Search failed')).toBeTruthy());
		expect(screen.getByText('Network error')).toBeTruthy();
	});

	it('shows success toast after adding a track', async () => {
		vi.mocked(apiClient.searchSongs).mockResolvedValue({
			provider: 'spotify',
			query: 'test',
			tracks: [makeTrack()]
		});
		const onAddTrack = vi.fn().mockResolvedValue(undefined);

		render(SongSearchPanel, { roomId: 'room-1', onAddTrack });

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'test' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

		await waitFor(() => expect(screen.getByRole('button', { name: 'Add to queue' })).toBeTruthy());
		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue' }));

		await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Added to queue'));
		expect(onAddTrack).toHaveBeenCalledTimes(1);
	});

	it('shows error toast when adding a track fails', async () => {
		vi.mocked(apiClient.searchSongs).mockResolvedValue({
			provider: 'spotify',
			query: 'test',
			tracks: [makeTrack()]
		});
		const onAddTrack = vi.fn().mockRejectedValue(new Error('Connection lost'));

		render(SongSearchPanel, { roomId: 'room-1', onAddTrack });

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'test' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

		await waitFor(() => expect(screen.getByRole('button', { name: 'Add to queue' })).toBeTruthy());
		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue' }));

		await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Connection lost'));
	});

	it('shows neutral toast for duplicate-queue error', async () => {
		vi.mocked(apiClient.searchSongs).mockResolvedValue({
			provider: 'spotify',
			query: 'test',
			tracks: [makeTrack()]
		});
		const onAddTrack = vi.fn().mockRejectedValue(new Error('Song is already in the queue'));

		render(SongSearchPanel, { roomId: 'room-1', onAddTrack });

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'test' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

		await waitFor(() => expect(screen.getByRole('button', { name: 'Add to queue' })).toBeTruthy());
		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue' }));

		await waitFor(() => expect(toast.message).toHaveBeenCalledWith('Song is already in the queue'));
		expect(toast.error).not.toHaveBeenCalled();
	});

	it('disables add button for tracks already in queue', async () => {
		const track = makeTrack();
		vi.mocked(apiClient.searchSongs).mockResolvedValue({
			provider: 'spotify',
			query: 'test',
			tracks: [track]
		});

		render(SongSearchPanel, {
			roomId: 'room-1',
			queuedTrackIds: new Set([track.trackId])
		});

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'test' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

		await waitFor(() =>
			expect(screen.getByRole('button', { name: 'Already in queue' })).toBeTruthy()
		);
		expect(
			(screen.getByRole('button', { name: 'Already in queue' }) as HTMLButtonElement).disabled
		).toBe(true);
	});

	it('clears results when query drops below 2 chars', async () => {
		vi.mocked(apiClient.searchSongs).mockResolvedValue({
			provider: 'spotify',
			query: 'test',
			tracks: [makeTrack()]
		});

		render(SongSearchPanel, { roomId: 'room-1' });

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'test' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));
		await waitFor(() => expect(screen.getByText('Test Song')).toBeTruthy());

		await fireEvent.input(screen.getByLabelText('Search songs'), {
			target: { value: 'a' }
		});

		await waitFor(() => expect(screen.queryByText('Test Song')).toBeNull());
	});
});
