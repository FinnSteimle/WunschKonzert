import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlaybackHistoryEntryDto, RoomStateDto, TrackDto } from '$lib/types/api';
import { toast } from 'svelte-sonner';
import SongHistoryModal from './SongHistoryModal.svelte';

vi.mock('svelte-sonner', () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
		message: vi.fn()
	}
}));

const trackA: TrackDto = {
	trackId: 't-old',
	providerTrackId: 'spotify:old',
	title: 'Older',
	artist: 'A',
	album: 'Album',
	duration: 60_000,
	coverUrl: '',
	deepLink: ''
};
const trackB: TrackDto = {
	trackId: 't-new',
	providerTrackId: 'spotify:new',
	title: 'Newer',
	artist: 'B',
	album: 'Album',
	duration: 60_000,
	coverUrl: '',
	deepLink: ''
};

const historyOldFirst: PlaybackHistoryEntryDto[] = [
	{ historyId: 1, playedAt: '2025-01-01T10:00:00Z', track: trackA },
	{ historyId: 2, playedAt: '2025-01-02T10:00:00Z', track: trackB }
];

function roomWithHistory(
	history: PlaybackHistoryEntryDto[],
	queue: RoomStateDto['queue'] = []
): RoomStateDto {
	return {
		room: {
			roomId: 'r1',
			joinCode: 'AB12CD',
			name: 'Room',
			status: 'open',
			createdAt: '2025-01-01T00:00:00Z',
			supportedProviderId: 'spotify'
		},
		host: { userId: 'h1', displayName: 'Host', createdAt: '2025-01-01T00:00:00Z' },
		users: [],
		queue,
		history
	};
}

describe('SongHistoryModal', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('opens dialog and sorts history newest first', async () => {
		render(SongHistoryModal, {
			roomState: roomWithHistory(historyOldFirst),
			onAddTrack: vi.fn()
		});

		await fireEvent.click(screen.getByRole('button', { name: /History/i }));

		await waitFor(() => {
			expect(screen.getByRole('heading', { name: 'Song History' })).toBeTruthy();
		});

		const items = screen.getAllByRole('listitem');
		expect(items[0].textContent).toContain('Newer');
		expect(items[1].textContent).toContain('Older');
	});

	it('shows empty state when no history', async () => {
		render(SongHistoryModal, { roomState: roomWithHistory([]), onAddTrack: vi.fn() });
		await fireEvent.click(screen.getByRole('button', { name: /History/i }));
		await waitFor(() => {
			expect(screen.getByText('No songs played yet')).toBeTruthy();
		});
	});

	it('marks track as in queue when matching queue entry', async () => {
		const queueEntry = {
			queueEntryId: 'q1',
			track: trackB,
			addedBy: { userId: 'u1', displayName: 'X' },
			queuedAt: '2025-01-01T00:00:00Z',
			position: 0,
			status: 'queued',
			voteScore: 0,
			orderRank: 0,
			feedback: []
		};
		render(SongHistoryModal, {
			roomState: roomWithHistory(
				[{ historyId: 1, playedAt: '2025-01-02T10:00:00Z', track: trackB }],
				[queueEntry]
			),
			onAddTrack: vi.fn()
		});
		await fireEvent.click(screen.getByRole('button', { name: /History/i }));
		await waitFor(() => {
			expect(screen.getByText('In queue')).toBeTruthy();
		});
	});

	it('toasts success after re-add', async () => {
		const onAddTrack = vi.fn().mockResolvedValue(undefined);
		render(SongHistoryModal, {
			roomState: roomWithHistory([
				{ historyId: 1, playedAt: '2025-01-02T10:00:00Z', track: trackB }
			]),
			onAddTrack
		});
		await fireEvent.click(screen.getByRole('button', { name: /History/i }));
		await waitFor(() => screen.getByText('Newer'));

		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue again' }));

		await waitFor(() => {
			expect(onAddTrack).toHaveBeenCalledWith(trackB);
			expect(toast.success).toHaveBeenCalledWith('Added to queue');
		});
	});

	it('toasts message for duplicate-queue error string', async () => {
		const onAddTrack = vi.fn().mockRejectedValue(new Error('Song is already in the queue'));
		render(SongHistoryModal, {
			roomState: roomWithHistory([
				{ historyId: 1, playedAt: '2025-01-02T10:00:00Z', track: trackB }
			]),
			onAddTrack
		});
		await fireEvent.click(screen.getByRole('button', { name: /History/i }));
		await waitFor(() => screen.getByText('Newer'));

		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue again' }));

		await waitFor(() => {
			expect(toast.message).toHaveBeenCalledWith('Song is already in the queue');
		});
	});

	it('toasts generic error string on failure', async () => {
		const onAddTrack = vi.fn().mockRejectedValue(new Error('network'));
		render(SongHistoryModal, {
			roomState: roomWithHistory([
				{ historyId: 1, playedAt: '2025-01-02T10:00:00Z', track: trackB }
			]),
			onAddTrack
		});
		await fireEvent.click(screen.getByRole('button', { name: /History/i }));
		await waitFor(() => screen.getByText('Newer'));

		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue again' }));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith('network');
		});
	});

	it('toasts fallback when rejection is not Error', async () => {
		const onAddTrack = vi.fn().mockRejectedValue('boom');
		render(SongHistoryModal, {
			roomState: roomWithHistory([
				{ historyId: 1, playedAt: '2025-01-02T10:00:00Z', track: trackB }
			]),
			onAddTrack
		});
		await fireEvent.click(screen.getByRole('button', { name: /History/i }));
		await waitFor(() => screen.getByText('Newer'));

		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue again' }));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith('Could not add song');
		});
	});
});
