export interface MusicPlayerState {
	isReady: boolean;
	isPlaying: boolean;
	trackId: string | null;
	positionMs: number;
	durationMs: number;
	/** True when the player detects the current track finished naturally. */
	trackEnded: boolean;
}

export interface MusicPlayer {
	connect(): Promise<void>;
	disconnect(): void;
	play(providerTrackId: string, positionMs?: number): Promise<void>;
	pause(): Promise<void>;
	resume(): Promise<void>;
	seekTo(positionMs: number): Promise<void>;
	getPositionMs(): Promise<number>;
	onStateChange(cb: (state: MusicPlayerState) => void): void;
}
