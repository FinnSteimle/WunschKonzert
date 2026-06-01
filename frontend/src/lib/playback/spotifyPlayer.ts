import { apiClient, isNeedsRelinkError } from '$lib/api/client';
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

export type SpotifyPlayerOptions = {
	onNeedsRelink?: () => void;
};

export class SpotifyPlayer implements MusicPlayer {
	private player: Spotify.Player | null = null;
	private deviceId: string | null = null;
	private userId: string;
	private onNeedsRelink?: () => void;
	private currentToken: string | null = null;
	private stateCallback: ((state: MusicPlayerState) => void) | null = null;
	private disposed = false;
	private authFailed = false;
	private lastTrackId: string | null = null;
	private wasPlaying = false;
	private hasPlayedPastStart = false;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private reconnectAttempts = 0;
	private connectionPromise: Promise<boolean> | null = null;
	private readyWaiters = new Set<{
		resolve: () => void;
		reject: (err: Error) => void;
	}>();

	constructor(userId: string, options?: SpotifyPlayerOptions) {
		this.userId = userId;
		this.onNeedsRelink = options?.onNeedsRelink;
	}

	async connect(): Promise<void> {
		if (this.authFailed) return;
		ensureSdkScript();
		if (!sdkReady) await sdkReadyPromise;
		if (this.disposed || this.authFailed) return;

		if (!this.player) {
			this.player = new Spotify.Player({
				name: 'WunschKonzert',
				getOAuthToken: (cb) => {
					void this.fetchToken()
						.then((token) => {
							if (!this.authFailed) cb(token);
						})
						.catch((err) => {
							console.error('[SpotifyPlayer] getOAuthToken failed:', err);
						});
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
				if (!this.authFailed) this.scheduleReconnect();
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

			this.player.addListener('authentication_error', (err) => {
				console.error('[SpotifyPlayer] authentication_error:', err.message);
				this.handleNeedsRelink();
			});

			const errorEvents = [
				'initialization_error',
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
		if (!this.player || this.disposed || this.authFailed) return false;
		if (this.connectionPromise) return this.connectionPromise;

		this.connectionPromise = this.player
			.connect()
			.then((connected) => {
				if (!connected && !this.disposed && !this.authFailed) {
					this.scheduleReconnect();
				}
				return connected;
			})
			.catch((err) => {
				if (!this.disposed && !this.authFailed) {
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
		if (this.disposed || this.authFailed || !this.player || this.reconnectTimer) return;
		const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 10000);
		this.reconnectAttempts += 1;
		this.reconnectTimer = setTimeout(() => {
			this.reconnectTimer = null;
			void this.connectInternal();
		}, delay);
	}

	private handleNeedsRelink(): void {
		if (this.authFailed || this.disposed) return;
		this.authFailed = true;
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
		this.deviceId = null;
		this.emitState({ isReady: false });
		this.rejectReadyWaiters(new Error('Spotify link expired'));
		this.onNeedsRelink?.();
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
		if (this.authFailed) {
			throw new Error('Spotify link expired');
		}
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
		if (this.authFailed) {
			throw new Error('Spotify link expired');
		}
		try {
			const { access_token } = await apiClient.getSpotifyToken(this.userId);
			this.currentToken = access_token;
			return access_token;
		} catch (err) {
			if (isNeedsRelinkError(err)) {
				this.handleNeedsRelink();
			}
			throw err;
		}
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
		if (this.authFailed) {
			throw new Error('Spotify link expired');
		}
		if (this.deviceId) return;

		await this.connectInternal();
		if (this.deviceId) return;
		if (this.authFailed) {
			throw new Error('Spotify link expired');
		}

		await new Promise<void>((resolve, reject) => {
			let timeout: ReturnType<typeof setTimeout> | null = null;
			const waiter = {
				resolve: () => {
					if (timeout) clearTimeout(timeout);
					this.readyWaiters.delete(waiter);
					resolve();
				},
				reject: (err: Error) => {
					if (timeout) clearTimeout(timeout);
					this.readyWaiters.delete(waiter);
					reject(err);
				}
			};
			timeout = setTimeout(() => {
				waiter.reject(new Error('Spotify player not ready'));
			}, timeoutMs);

			this.readyWaiters.add(waiter);
			if (this.deviceId) waiter.resolve();
			else if (this.authFailed) waiter.reject(new Error('Spotify link expired'));
		});
	}

	private flushReadyWaiters(): void {
		for (const waiter of this.readyWaiters) waiter.resolve();
		this.readyWaiters.clear();
	}

	private rejectReadyWaiters(err: Error): void {
		for (const waiter of this.readyWaiters) waiter.reject(err);
		this.readyWaiters.clear();
	}
}
