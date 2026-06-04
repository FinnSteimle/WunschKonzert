declare namespace MusicKit {
	interface AppInfo {
		name: string;
		build: string;
	}

	interface MusicKitConfig {
		developerToken: string;
		musicUserToken?: string;
		suppressErrorDialog?: boolean;
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

	interface MusicKitInstance {
		authorize(): Promise<string>;
		musicUserToken: string;
		isAuthorized: boolean;
		play(): Promise<void>;
		pause(): Promise<void>;
		seekToTime(time: number): Promise<void>;
		currentPlaybackTime: number;
		currentPlaybackDuration: number;
		playbackState: number;
		nowPlayingItem: MediaItem | null;
		setQueue(options: {
			song?: string;
			songs?: string[];
			startPlaying?: boolean;
		}): Promise<void>;
		addEventListener(event: string, listener: (...args: unknown[]) => void): void;
		removeEventListener(event: string, listener: (...args: unknown[]) => void): void;
	}

	interface MusicKitStatic {
		configure(config: MusicKitConfig): MusicKitInstance | Promise<MusicKitInstance>;
		getInstance(): MusicKitInstance | undefined;
	}
}

interface Window {
	MusicKit?: MusicKit.MusicKitStatic;
}
