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

function toSpotifyTrackUri(providerTrackId: string): string {
	if (providerTrackId.startsWith('spotify:track:')) return providerTrackId;
	if (providerTrackId.startsWith('spotify:')) {
		return `spotify:track:${providerTrackId.slice('spotify:'.length)}`;
	}
	return `spotify:track:${providerTrackId}`;
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
	private hasPlayedPastStart = false;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private reconnectAttempts = 0;
	private connectionPromise: Promise<boolean> | null = null;
	private readyWaiters = new Set<() => void>();

	constructor(userId: string) {
		this.userId = userId;
	}

	async connect(): Promise<void> {
		ensureSdkScript();
		if (!sdkReady) await sdkReadyPromise;
		if (this.disposed) return;

		if (!this.player) {
			this.player = new Spotify.Player({
				name: 'WunschKonzert',
				getOAuthToken: (cb) => {
					this.fetchToken().then((token) => cb(token));
				},
				volume: 0.5
			});

			this.player.addListener('ready', ({ device_id }) => {
				this.deviceId = device_id;
				this.reconnectAttempts = 0;
				if (this.reconnectTimer) {
					clearTimeout(this.reconnectTimer);
					this.reconnectTimer = null;
				}
				// Force a pause on ready to prevent Spotify's auto-resume behavior
				// in some browsers/accounts.
				this.player?.getCurrentState().then((state) => {
					if (state && !state.paused) {
						this.player?.pause().catch(() => {});
					}
				});
				this.flushReadyWaiters();
				this.emitState({ isReady: true });
			});

			this.player.addListener('not_ready', () => {
				this.deviceId = null;
				this.emitState({ isReady: false });
				this.scheduleReconnect();
			});

			this.player.addListener('player_state_changed', (state) => {
				if (!state) return;
				const track = state.track_window.current_track;
				const playing = !state.paused;

				// Track whether we've played past the start (position > 1000ms) at least once.
				// This helps distinguish between:
				// - Track just started (position === 0, hasn't played yet)
				// - Track ended and wrapped to next track (position === 0, but we had played)
				if (playing && state.position > 1000) {
					this.hasPlayedPastStart = true;
				}

				// Detect natural track end: was playing -> now paused, and either
				// position wrapped to 0 (after having played) or reached track end.
				const ended =
					this.wasPlaying &&
					!playing &&
					state.duration > 0 &&
					((state.position === 0 && this.hasPlayedPastStart) ||
						state.position >= state.duration - 500);

				// Reset hasPlayedPastStart when track changes or playback stops
				if (!playing || track?.id !== this.lastTrackId) {
					this.hasPlayedPastStart = false;
				}

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
		}

		await this.connectInternal();
	}

	private async connectInternal(): Promise<boolean> {
		if (!this.player || this.disposed) return false;
		if (this.connectionPromise) return this.connectionPromise;

		this.connectionPromise = this.player
			.connect()
			.then((connected) => {
				if (!connected && !this.disposed) {
					this.scheduleReconnect();
				}
				return connected;
			})
			.catch((err) => {
				if (!this.disposed) {
					console.error('[SpotifyPlayer] connect failed:', err);
					this.scheduleReconnect();
				}
				return false;
			})
			.finally(() => {
				this.connectionPromise = null;
			});

		return this.connectionPromise;
	}

	private scheduleReconnect(): void {
		if (this.disposed || !this.player || this.reconnectTimer) return;
		const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 10000);
		this.reconnectAttempts += 1;
		this.reconnectTimer = setTimeout(() => {
			this.reconnectTimer = null;
			void this.connectInternal();
		}, delay);
	}

	disconnect(): void {
		this.disposed = true;
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
		this.readyWaiters.clear();
		this.player?.disconnect();
		this.player = null;
		this.deviceId = null;
	}

	async play(providerTrackId: string, positionMs?: number): Promise<void> {
		const token = await this.fetchToken();
		await this.waitForReady();
		if (!this.deviceId) throw new Error('Spotify player not ready');

		const body: Record<string, unknown> = {
			uris: [toSpotifyTrackUri(providerTrackId)]
		};
		if (positionMs !== undefined) {
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

	private async waitForReady(timeoutMs = 10000): Promise<void> {
		if (this.deviceId) return;

		await this.connectInternal();
		if (this.deviceId) return;

		await new Promise<void>((resolve, reject) => {
			let timeout: ReturnType<typeof setTimeout> | null = null;
			const onReady = () => {
				if (timeout) clearTimeout(timeout);
				this.readyWaiters.delete(onReady);
				resolve();
			};
			timeout = setTimeout(() => {
				this.readyWaiters.delete(onReady);
				reject(new Error('Spotify player not ready'));
			}, timeoutMs);

			this.readyWaiters.add(onReady);
			if (this.deviceId) onReady();
		});
	}

	private flushReadyWaiters(): void {
		for (const resolve of this.readyWaiters) resolve();
		this.readyWaiters.clear();
	}
}
