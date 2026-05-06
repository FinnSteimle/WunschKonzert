import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { TrackDto } from '$lib/types/api';
import HistoryItem from './HistoryItem.svelte';

const baseTrack: TrackDto = {
	trackId: 't1',
	providerTrackId: 'spotify:t1',
	title: 'Song',
	artist: 'Artist',
	album: 'Album',
	duration: 60_000,
	coverUrl: 'https://example.com/cover.jpg',
	deepLink: ''
};

describe('HistoryItem', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2025-06-15T12:00:00.000Z'));
	});

	afterEach(() => {
		vi.restoreAllMocks();
		vi.useRealTimers();
	});

	it('renders track info and cover', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:50:00.000Z'
		});
		expect(screen.getByText('Song')).toBeTruthy();
		expect(screen.getByText('Artist')).toBeTruthy();
		expect(screen.getByAltText('')).toBeTruthy();
	});

	it('shows No art placeholder when coverUrl missing', () => {
		render(HistoryItem, {
			track: { ...baseTrack, coverUrl: '' },
			playedAt: '2025-06-15T11:50:00.000Z'
		});
		expect(screen.getByText('No art')).toBeTruthy();
	});

	it('formats played time: just now under 1 minute', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:59:30.000Z'
		});
		expect(screen.getByText(/Played just now/)).toBeTruthy();
	});

	it('formats played time in minutes', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:55:00.000Z'
		});
		expect(screen.getByText(/Played 5m ago/)).toBeTruthy();
	});

	it('formats played time in hours under 24h', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T09:00:00.000Z'
		});
		expect(screen.getByText(/Played 3h ago/)).toBeTruthy();
	});

	it('uses locale date string when older than 24 hours', () => {
		vi.spyOn(Date.prototype, 'toLocaleDateString').mockReturnValue('historic-date');
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-01T12:00:00.000Z'
		});
		expect(screen.getByText(/Played historic-date/)).toBeTruthy();
	});

	it('falls back to plain "Played" when playedAt null', () => {
		render(HistoryItem, { track: baseTrack, playedAt: null });
		expect(
			screen.getByText((_t, el) => el?.tagName === 'P' && el.textContent?.trim() === 'Played')
		).toBeTruthy();
	});

	it('shows In queue badge', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:00:00.000Z',
			inQueue: true
		});
		expect(screen.getByText('In queue')).toBeTruthy();
	});

	it('calls onAdd when button clicked', async () => {
		const onAdd = vi.fn();
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:00:00.000Z',
			onAdd
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Add to queue again' }));
		expect(onAdd).toHaveBeenCalledOnce();
	});

	it('disables add when in queue', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:00:00.000Z',
			inQueue: true,
			onAdd: vi.fn()
		});
		expect((screen.getByRole('button', { name: 'Already in queue' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});

	it('disables add while adding', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:00:00.000Z',
			inQueue: false,
			adding: true,
			onAdd: vi.fn()
		});
		expect((screen.getByRole('button', { name: 'Add to queue again' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});

	it('disables add when handler missing', () => {
		render(HistoryItem, {
			track: baseTrack,
			playedAt: '2025-06-15T11:00:00.000Z'
		});
		expect((screen.getByRole('button', { name: 'Add to queue again' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});
});
