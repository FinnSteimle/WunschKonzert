import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PlaybackControls from './PlaybackControls.svelte';

describe('PlaybackControls', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows Resume when playback is paused', () => {
		render(PlaybackControls, { playbackState: 'paused' });
		expect(screen.getByRole('button', { name: /resume/i })).toBeTruthy();
	});

	it('shows Pause when playback is playing', () => {
		render(PlaybackControls, { playbackState: 'playing' });
		expect(screen.getByRole('button', { name: /pause/i })).toBeTruthy();
	});

	it('shows Resume when playback is stopped', () => {
		render(PlaybackControls, { playbackState: 'stopped' });
		expect(screen.getByRole('button', { name: /resume/i })).toBeTruthy();
	});

	it('calls onPlaybackAction with pause when playing and clicked', async () => {
		const onPlaybackAction = vi.fn();
		render(PlaybackControls, { playbackState: 'playing', onPlaybackAction });

		await fireEvent.click(screen.getByRole('button', { name: /pause/i }));

		expect(onPlaybackAction).toHaveBeenCalledWith('pause');
	});

	it('calls onPlaybackAction with resume when paused and clicked', async () => {
		const onPlaybackAction = vi.fn();
		render(PlaybackControls, { playbackState: 'paused', onPlaybackAction });

		await fireEvent.click(screen.getByRole('button', { name: /resume/i }));

		expect(onPlaybackAction).toHaveBeenCalledWith('resume');
	});

	it('disables the button when disabled prop is true', () => {
		render(PlaybackControls, { playbackState: 'playing', disabled: true });
		const btn = screen.getByRole('button') as HTMLButtonElement;
		expect(btn.disabled).toBe(true);
	});

	it('disables the button when busy prop is true', () => {
		render(PlaybackControls, { playbackState: 'playing', busy: true });
		const btn = screen.getByRole('button') as HTMLButtonElement;
		expect(btn.disabled).toBe(true);
	});
});
