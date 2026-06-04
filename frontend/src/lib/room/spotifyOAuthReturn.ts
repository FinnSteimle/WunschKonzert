export const SPOTIFY_OAUTH_QUERY_KEYS = [
	'spotify_linked',
	'spotify_error',
	'spotify_profile_warning'
] as const;

export const SPOTIFY_LINK_TOAST_KEY = 'wk_spotify_link_toast';

export type SpotifyLinkToast = {
	type: 'success' | 'message' | 'error';
	message: string;
};

export function buildPathWithoutSpotifyOAuthParams(href: string): string {
	const url = new URL(href);
	for (const key of SPOTIFY_OAUTH_QUERY_KEYS) {
		url.searchParams.delete(key);
	}
	const search = url.searchParams.toString();
	return search ? `${url.pathname}?${search}` : url.pathname;
}

export function hasSpotifyOAuthQueryParams(params: URLSearchParams): boolean {
	return (
		params.get('spotify_error') !== null ||
		params.get('spotify_linked') === 'true' ||
		params.get('spotify_profile_warning') !== null
	);
}

export function writeSpotifyLinkToast(toast: SpotifyLinkToast): void {
	sessionStorage.setItem(SPOTIFY_LINK_TOAST_KEY, JSON.stringify(toast));
}

export function readAndClearSpotifyLinkToast(): SpotifyLinkToast | null {
	const raw = sessionStorage.getItem(SPOTIFY_LINK_TOAST_KEY);
	if (!raw) return null;
	sessionStorage.removeItem(SPOTIFY_LINK_TOAST_KEY);
	try {
		return JSON.parse(raw) as SpotifyLinkToast;
	} catch {
		return null;
	}
}

export function spotifyErrorHint(spotifyError: string): string {
	return spotifyError === 'profile_fetch_failed'
		? ' Add your Spotify email under Users in the Spotify Developer Dashboard (development mode), then link again.'
		: '';
}

export function toastPayloadAfterSpotifyLink(
	linked: boolean,
	profileWarning: string | null
): SpotifyLinkToast {
	if (linked) {
		if (profileWarning === 'profile_fetch_failed') {
			return {
				type: 'message',
				message:
					'Spotify linked for playback. Profile lookup failed. Add your Spotify account under Users in the Spotify Developer Dashboard if playback fails.'
			};
		}
		return { type: 'success', message: 'Spotify account linked' };
	}
	return {
		type: 'error',
		message:
			'Spotify login finished but this browser is still not linked on the server. Check API URL / redirect URI, then link again.'
	};
}
