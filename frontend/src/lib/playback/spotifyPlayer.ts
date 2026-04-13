import { apiClient } from '$lib/api/client';
import type { MusicPlayer, MusicPlayerState } from './types';

const SDK_SCRIPT_URL = 'https://sdk.scdn.co/spotify-player.js';
const SPOTIFY_PLAY_URL = 'https://api.spotify.com/v1/me/player/play';

let sdkLoaded = false;
let sdkReady = false;
let sdkReadyPromiseResolve: (() => void) | null = null;
const sdkReadyPromise = new Promise<void>((resolve) => {
	sdkReadyPromiseResolve = resolve;
});

function ensureSdkScript(): void {
	if (sdkLoaded) return;
	sdkLoaded = true;

	window.onSpotifyWebPlaybackSDKReady = () => {
		sdkReady = true;
		sdkReadyPromiseResolve?.();
	};

	const script = document.createElement('script');
	script.src = SDK_SCRIPT_URL;
	script.async = true;
	document.head.appendChild(script);
}

export class SpotifyPlayer implements MusicPlayer {
	private player: Spotify.Player | null = null;
	private deviceId: string | null = null;
	private userId: string;
	private currentToken: string | null = null;
	private stateCallback: ((state: MusicPlayerState) => void) | null = null;
	private disposed = false;
	private lastTrackId: string | null = null;
	private wasPlaying = false;

	constructor(userId: string) {
		this.userId = userId;
	}

	async connect(): Promise<void> {
		ensureSdkScript();
		if (!sdkReady) await sdkReadyPromise;
		if (this.disposed) return;

		this.player = new Spotify.Player({
			name: 'WunschKonzert',
			getOAuthToken: (cb) => {
				this.fetchToken().then((token) => cb(token));
			},
			volume: 0.5
		});

		this.player.addListener('ready', ({ device_id }) => {
			this.deviceId = device_id;
			this.emitState({ isReady: true });
		});

		this.player.addListener('not_ready', () => {
			this.deviceId = null;
			this.emitState({ isReady: false });
		});

		this.player.addListener('player_state_changed', (state) => {
			if (!state) return;
			const track = state.track_window.current_track;
			const playing = !state.paused;

			// Detect natural track end: was playing -> now paused, and either
			// position wrapped to 0 or reached the end of the track.
			const ended =
				this.wasPlaying &&
				!playing &&
				state.duration > 0 &&
				(state.position === 0 || state.position >= state.duration - 500);

			this.wasPlaying = playing;
			this.lastTrackId = track?.id ?? null;
			this.emitState({
				isReady: true,
				isPlaying: playing,
				trackId: track?.id ?? null,
				positionMs: state.position,
				durationMs: state.duration,
				trackEnded: ended
			});
		});

		const errorEvents = [
			'initialization_error',
			'authentication_error',
			'account_error',
			'playback_error'
		] as const;
		for (const event of errorEvents) {
			this.player.addListener(event, (err) => {
				console.error(`[SpotifyPlayer] ${event}:`, err.message);
			});
		}

		await this.player.connect();
	}

	disconnect(): void {
		this.disposed = true;
		this.player?.disconnect();
		this.player = null;
		this.deviceId = null;
	}

	async play(providerTrackId: string, positionMs?: number): Promise<void> {
		const token = await this.fetchToken();
		if (!this.deviceId) throw new Error('Spotify player not ready');

		const body: Record<string, unknown> = {
			uris: [`spotify:track:${providerTrackId}`]
		};
		if (positionMs !== undefined && positionMs > 0) {
			body.position_ms = Math.round(positionMs);
		}

		const resp = await fetch(`${SPOTIFY_PLAY_URL}?device_id=${this.deviceId}`, {
			method: 'PUT',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(body)
		});
		if (!resp.ok && resp.status !== 204) {
			throw new Error(`Spotify play failed: ${resp.status}`);
		}
	}

	async pause(): Promise<void> {
		await this.player?.pause();
	}

	async resume(): Promise<void> {
		await this.player?.resume();
	}

	async seekTo(positionMs: number): Promise<void> {
		await this.player?.seek(positionMs);
	}

	async getPositionMs(): Promise<number> {
		const state = await this.player?.getCurrentState();
		return state?.position ?? 0;
	}

	onStateChange(cb: (state: MusicPlayerState) => void): void {
		this.stateCallback = cb;
	}

	getLastTrackId(): string | null {
		return this.lastTrackId;
	}

	isReady(): boolean {
		return this.deviceId !== null;
	}

	private async fetchToken(): Promise<string> {
		const { access_token } = await apiClient.getSpotifyToken(this.userId);
		this.currentToken = access_token;
		return access_token;
	}

	private emitState(partial: Partial<MusicPlayerState>): void {
		if (!this.stateCallback) return;
		this.stateCallback({
			isReady: partial.isReady ?? this.deviceId !== null,
			isPlaying: partial.isPlaying ?? false,
			trackId: partial.trackId ?? this.lastTrackId,
			positionMs: partial.positionMs ?? 0,
			durationMs: partial.durationMs ?? 0,
			trackEnded: partial.trackEnded ?? false
		});
	}
}
