declare namespace Spotify {
	interface Album {
		uri: string;
		name: string;
		images: Array<{ url: string }>;
	}

	interface Artist {
		uri: string;
		name: string;
	}

	interface Track {
		uri: string;
		id: string | null;
		type: 'track' | 'episode' | 'ad';
		media_type: 'audio' | 'video';
		name: string;
		is_playable: boolean;
		album: Album;
		artists: Artist[];
		duration_ms: number;
	}

	interface PlaybackDisallows {
		pausing?: boolean;
		peeking_next?: boolean;
		peeking_prev?: boolean;
		resuming?: boolean;
		seeking?: boolean;
		skipping_next?: boolean;
		skipping_prev?: boolean;
	}

	interface PlaybackState {
		context: {
			uri: string | null;
			metadata: Record<string, unknown> | null;
		};
		disallows: PlaybackDisallows;
		duration: number;
		paused: boolean;
		position: number;
		repeat_mode: number;
		shuffle: boolean;
		track_window: {
			current_track: Track;
			previous_tracks: Track[];
			next_tracks: Track[];
		};
	}

	interface WebPlaybackError {
		message: string;
	}

	type GetOAuthTokenCallback = (cb: (token: string) => void) => void;

	interface PlayerInit {
		name: string;
		getOAuthToken: GetOAuthTokenCallback;
		volume?: number;
	}

	class Player {
		constructor(options: PlayerInit);

		connect(): Promise<boolean>;
		disconnect(): void;
		pause(): Promise<void>;
		resume(): Promise<void>;
		togglePlay(): Promise<void>;
		seek(positionMs: number): Promise<void>;
		getCurrentState(): Promise<PlaybackState | null>;
		setName(name: string): Promise<void>;
		getVolume(): Promise<number>;
		setVolume(volume: number): Promise<void>;

		addListener(event: 'ready', cb: (data: { device_id: string }) => void): void;
		addListener(event: 'not_ready', cb: (data: { device_id: string }) => void): void;
		addListener(event: 'player_state_changed', cb: (state: PlaybackState | null) => void): void;
		addListener(
			event: 'initialization_error' | 'authentication_error' | 'account_error' | 'playback_error',
			cb: (error: WebPlaybackError) => void
		): void;

		removeListener(event: string, cb?: (...args: unknown[]) => void): void;
	}
}

interface Window {
	Spotify?: typeof Spotify;
	onSpotifyWebPlaybackSDKReady?: () => void;
}
