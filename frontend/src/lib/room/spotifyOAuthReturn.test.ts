import { beforeEach, describe, expect, it } from 'vitest';
import {
	SPOTIFY_LINK_TOAST_KEY,
	buildPathWithoutSpotifyOAuthParams,
	hasSpotifyOAuthQueryParams,
	readAndClearSpotifyLinkToast,
	spotifyErrorHint,
	toastPayloadAfterSpotifyLink,
	writeSpotifyLinkToast
} from './spotifyOAuthReturn';

describe('spotifyOAuthReturn', () => {
	beforeEach(() => {
		sessionStorage.clear();
	});

	it('buildPathWithoutSpotifyOAuthParams strips spotify query keys', () => {
		const href = 'http://localhost:5173/room/AB2CD3?spotify_linked=true&foo=bar';
		expect(buildPathWithoutSpotifyOAuthParams(href)).toBe('/room/AB2CD3?foo=bar');
	});

	it('buildPathWithoutSpotifyOAuthParams returns pathname only when empty', () => {
		expect(
			buildPathWithoutSpotifyOAuthParams('http://localhost:5173/room/AB2CD3?spotify_linked=true')
		).toBe('/room/AB2CD3');
	});

	it('hasSpotifyOAuthQueryParams detects oauth return params', () => {
		expect(hasSpotifyOAuthQueryParams(new URLSearchParams('spotify_linked=true'))).toBe(true);
		expect(hasSpotifyOAuthQueryParams(new URLSearchParams('spotify_error=denied'))).toBe(true);
		expect(hasSpotifyOAuthQueryParams(new URLSearchParams())).toBe(false);
	});

	it('writes and reads spotify link toast from sessionStorage', () => {
		writeSpotifyLinkToast({ type: 'success', message: 'Spotify account linked' });
		expect(readAndClearSpotifyLinkToast()).toEqual({
			type: 'success',
			message: 'Spotify account linked'
		});
		expect(sessionStorage.getItem(SPOTIFY_LINK_TOAST_KEY)).toBeNull();
	});

	it('returns null for malformed stored toast', () => {
		sessionStorage.setItem(SPOTIFY_LINK_TOAST_KEY, '{bad json');
		expect(readAndClearSpotifyLinkToast()).toBeNull();
	});

	it('spotifyErrorHint adds dashboard hint for profile_fetch_failed', () => {
		expect(spotifyErrorHint('profile_fetch_failed')).toContain('Spotify Developer Dashboard');
		expect(spotifyErrorHint('denied')).toBe('');
	});

	it('toastPayloadAfterSpotifyLink maps linked state and profile warning', () => {
		expect(toastPayloadAfterSpotifyLink(true, null).type).toBe('success');
		expect(toastPayloadAfterSpotifyLink(true, 'profile_fetch_failed').type).toBe('message');
		expect(toastPayloadAfterSpotifyLink(false, null).type).toBe('error');
	});
});
