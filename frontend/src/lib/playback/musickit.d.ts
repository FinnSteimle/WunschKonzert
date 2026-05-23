declare namespace MusicKit {
	interface AppInfo {
		name: string;
		build: string;
	}

	interface MusicKitConfig {
		developerToken: string;
		musicUserToken?: string;
		app: AppInfo;
	}

	interface MediaItem {
		id: string;
		attributes?: {
			name?: string;
			artistName?: string;
			durationInMillis?: number;
		};
	}

	interface Player {
		play(): Promise<void>;
		pause(): Promise<void>;
		seekToTime(time: number): Promise<void>;
		currentPlaybackTime: number;
		currentPlaybackDuration: number;
		playbackState: number;
		nowPlayingItem: MediaItem | null;
	}

	interface MusicKitInstance {
		authorize(): Promise<string>;
		musicUserToken: string;
		player: Player;
		setQueue(options: { songs: string[]; startPlaying?: boolean }): Promise<void>;
		addEventListener(event: string, listener: (...args: unknown[]) => void): void;
		removeEventListener(event: string, listener: (...args: unknown[]) => void): void;
	}

	interface MusicKitStatic {
		configure(config: MusicKitConfig): void;
		getInstance(): MusicKitInstance;
	}
}

interface Window {
	MusicKit?: MusicKit.MusicKitStatic;
}
