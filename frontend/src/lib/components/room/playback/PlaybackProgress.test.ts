import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import PlaybackProgress from './PlaybackProgress.svelte';

describe('PlaybackProgress', () => {
	it('renders position and duration in m:ss format', () => {
		render(PlaybackProgress, { positionMs: 65_000, durationMs: 210_000 });
		expect(screen.getByText('1:05')).toBeTruthy();
		expect(screen.getByText('3:30')).toBeTruthy();
	});

	it('formats zero correctly', () => {
		render(PlaybackProgress, { positionMs: 0, durationMs: 0 });
		const texts = screen.getAllByText('0:00');
		expect(texts.length).toBe(2);
	});

	it('formats single-digit seconds with padding', () => {
		render(PlaybackProgress, { positionMs: 3_000, durationMs: 60_000 });
		expect(screen.getByText('0:03')).toBeTruthy();
		expect(screen.getByText('1:00')).toBeTruthy();
	});

	it('handles negative positionMs gracefully', () => {
		render(PlaybackProgress, { positionMs: -1000, durationMs: 60_000 });
		expect(screen.getByText('0:00')).toBeTruthy();
	});

	it('shows playback state when provided', () => {
		render(PlaybackProgress, { positionMs: 0, durationMs: 60_000, state: 'playing' });
		expect(screen.getByText('playing')).toBeTruthy();
	});

	it('shows paused state', () => {
		render(PlaybackProgress, { positionMs: 30_000, durationMs: 60_000, state: 'paused' });
		expect(screen.getByText('paused')).toBeTruthy();
	});

	it('does not show state label when state is undefined', () => {
		const { container } = render(PlaybackProgress, { positionMs: 0, durationMs: 60_000 });
		expect(container.querySelector('.capitalize')).toBeNull();
	});

	it('has accessible label', () => {
		render(PlaybackProgress, { positionMs: 0, durationMs: 60_000 });
		expect(screen.getByLabelText('Playback progress')).toBeTruthy();
	});

	it('renders a progress bar', () => {
		render(PlaybackProgress, { positionMs: 30_000, durationMs: 60_000 });
		expect(screen.getByRole('progressbar')).toBeTruthy();
	});
});
