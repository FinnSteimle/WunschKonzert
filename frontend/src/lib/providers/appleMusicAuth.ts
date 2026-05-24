import { apiClient } from '$lib/api/client';

const MUSICKIT_SCRIPT_URL = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';

let scriptLoading: Promise<void> | null = null;

function loadMusicKitScript(): Promise<void> {
	if (typeof window === 'undefined') {
		return Promise.reject(new Error('MusicKit is only available in the browser'));
	}
	if (window.MusicKit) {
		return Promise.resolve();
	}
	if (scriptLoading) return scriptLoading;

	scriptLoading = new Promise<void>((resolve, reject) => {
		const onLoaded = () => {
			document.removeEventListener('musickitloaded', onLoaded);
			if (!window.MusicKit) {
				scriptLoading = null;
				reject(new Error('MusicKit failed to initialize'));
				return;
			}
			resolve();
		};
		document.addEventListener('musickitloaded', onLoaded);

		const existing = document.querySelector<HTMLScriptElement>(
			`script[src="${MUSICKIT_SCRIPT_URL}"]`
		);
		if (!existing) {
			const script = document.createElement('script');
			script.src = MUSICKIT_SCRIPT_URL;
			script.async = true;
			script.onerror = () => {
				document.removeEventListener('musickitloaded', onLoaded);
				scriptLoading = null;
				reject(new Error('Failed to load Apple MusicKit'));
			};
			document.head.appendChild(script);
		}
	});

	return scriptLoading;
}

export interface ConfigureMusicKitOptions {
	developerToken: string;
	musicUserToken?: string;
}

/** Configure MusicKit and return the singleton instance. */
export async function configureMusicKit(
	options: ConfigureMusicKitOptions
): Promise<MusicKit.MusicKitInstance> {
	await loadMusicKitScript();
	if (!window.MusicKit) {
		throw new Error('MusicKit failed to initialize');
	}

	const config: MusicKit.MusicKitConfig = {
		developerToken: options.developerToken,
		suppressErrorDialog: true,
		app: {
			name: 'WunschKonzert',
			build: '1.0'
		}
	};
	if (options.musicUserToken) {
		config.musicUserToken = options.musicUserToken;
	}

	const configured = window.MusicKit.configure(config);
	const instance =
		configured instanceof Promise
			? await configured
			: (configured ?? window.MusicKit.getInstance());

	if (!instance) {
		throw new Error('MusicKit instance not available after configure');
	}
	return instance;
}

/** Run MusicKit authorize flow and persist the Music User Token on the backend. */
export async function linkAppleMusicAccount(
	userId: string,
	displayName: string
): Promise<{ storefront: string; display_name: string | null }> {
	const { developer_token } = await apiClient.getAppleMusicDeveloperToken(userId);
	const music = await configureMusicKit({ developerToken: developer_token });
	const musicUserToken = await music.authorize();
	if (!musicUserToken) {
		throw new Error('Apple Music authorization was cancelled');
	}
	return apiClient.linkAppleMusic({
		user_id: userId,
		music_user_token: musicUserToken,
		display_name: displayName
	});
}

/** Restore MusicKit with stored MUT (for host playback). */
export async function configureMusicKitForUser(userId: string): Promise<MusicKit.MusicKitInstance> {
	const { developer_token } = await apiClient.getAppleMusicDeveloperToken(userId);
	let musicUserToken: string | undefined;
	try {
		const stored = await apiClient.getAppleMusicToken(userId);
		musicUserToken = stored.music_user_token;
	} catch {
		// Host playback requires a linked account; caller handles errors.
	}
	return configureMusicKit({ developerToken: developer_token, musicUserToken });
}
