import { configureMusicKitForUser } from '$lib/providers/appleMusicAuth';
import type { MusicPlayer, MusicPlayerState } from './types';

/** MusicKit playbackState values we care about. */
const PLAYBACK_PLAYING = 2;
const PLAYBACK_PAUSED = 3;
const PLAYBACK_ENDED = 5;
const PLAYBACK_COMPLETED = 6;

function toSongId(providerTrackId: string): string {
	if (providerTrackId.startsWith('apple:')) {
		return providerTrackId.slice('apple:'.length);
	}
	return providerTrackId;
}

export class AppleMusicPlayer implements MusicPlayer {
	private music: MusicKit.MusicKitInstance | null = null;
	private userId: string;
	private stateCallback: ((state: MusicPlayerState) => void) | null = null;
	private disposed = false;
	private lastTrackId: string | null = null;
	private wasPlaying = false;
	private hasPlayedPastStart = false;
	private onPlaybackStateChange: ((...args: unknown[]) => void) | null = null;
	private onNowPlayingChange: ((...args: unknown[]) => void) | null = null;

	constructor(userId: string) {
		this.userId = userId;
	}

	async connect(): Promise<void> {
		if (this.disposed) return;
		this.music = await configureMusicKitForUser(this.userId);
		this.attachListeners();
		this.emitState({ isReady: true });
	}

	disconnect(): void {
		this.disposed = true;
		if (this.music) {
			if (this.onPlaybackStateChange) {
				this.music.removeEventListener('playbackStateDidChange', this.onPlaybackStateChange);
			}
			if (this.onNowPlayingChange) {
				this.music.removeEventListener('nowPlayingItemDidChange', this.onNowPlayingChange);
			}
		}
		this.music?.player.pause().catch(() => {});
		this.music = null;
	}

	async play(providerTrackId: string, positionMs?: number): Promise<void> {
		if (!this.music) throw new Error('Apple Music player not ready');
		const songId = toSongId(providerTrackId);
		await this.music.setQueue({ songs: [songId], startPlaying: false });
		const seekSeconds = positionMs !== undefined ? Math.max(0, positionMs) / 1000 : 0;
		if (seekSeconds > 0) {
			await this.music.player.seekToTime(seekSeconds);
		}
		await this.music.player.play();
		this.lastTrackId = songId;
		this.hasPlayedPastStart = seekSeconds > 1;
		this.emitFromPlayer();
	}

	async pause(): Promise<void> {
		await this.music?.player.pause();
	}

	async resume(): Promise<void> {
		await this.music?.player.play();
	}

	async seekTo(positionMs: number): Promise<void> {
		await this.music?.player.seekToTime(Math.max(0, positionMs) / 1000);
	}

	async getPositionMs(): Promise<number> {
		const seconds = this.music?.player.currentPlaybackTime ?? 0;
		return Math.round(seconds * 1000);
	}

	onStateChange(cb: (state: MusicPlayerState) => void): void {
		this.stateCallback = cb;
	}

	getLastTrackId(): string | null {
		return this.lastTrackId;
	}

	private attachListeners(): void {
		if (!this.music) return;

		this.onPlaybackStateChange = () => this.emitFromPlayer();
		this.onNowPlayingChange = () => this.emitFromPlayer();

		this.music.addEventListener('playbackStateDidChange', this.onPlaybackStateChange);
		this.music.addEventListener('nowPlayingItemDidChange', this.onNowPlayingChange);
	}

	private emitFromPlayer(): void {
		if (!this.music) return;
		const player = this.music.player;
		const item = player.nowPlayingItem;
		const trackId = item?.id ?? null;
		const playbackState = player.playbackState;
		const playing = playbackState === PLAYBACK_PLAYING;
		const positionMs = Math.round(player.currentPlaybackTime * 1000);
		const durationMs = Math.round(player.currentPlaybackDuration * 1000);

		if (playing && positionMs > 1000) {
			this.hasPlayedPastStart = true;
		}

		const ended =
			this.wasPlaying &&
			!playing &&
			(playbackState === PLAYBACK_ENDED ||
				playbackState === PLAYBACK_COMPLETED ||
				(positionMs === 0 && this.hasPlayedPastStart) ||
				(durationMs > 0 && positionMs >= durationMs - 500));

		if (!playing || trackId !== this.lastTrackId) {
			this.hasPlayedPastStart = false;
		}

		this.wasPlaying = playing;
		this.lastTrackId = trackId;
		this.emitState({
			isReady: true,
			isPlaying: playing,
			trackId,
			positionMs,
			durationMs,
			trackEnded: ended
		});
	}

	private emitState(partial: Partial<MusicPlayerState>): void {
		if (!this.stateCallback) return;
		this.stateCallback({
			isReady: partial.isReady ?? this.music !== null,
			isPlaying: partial.isPlaying ?? false,
			trackId: partial.trackId ?? this.lastTrackId,
			positionMs: partial.positionMs ?? 0,
			durationMs: partial.durationMs ?? 0,
			trackEnded: partial.trackEnded ?? false
		});
	}
}
