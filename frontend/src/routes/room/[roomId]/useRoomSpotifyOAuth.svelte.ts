import { browser } from '$app/environment';
import { page } from '$app/state';
import type { ProviderId } from '$lib/types/api';
import {
	buildPathWithoutSpotifyOAuthParams,
	hasSpotifyOAuthQueryParams,
	readAndClearSpotifyLinkToast,
	spotifyErrorHint,
	toastPayloadAfterSpotifyLink,
	writeSpotifyLinkToast
} from '$lib/room/spotifyOAuthReturn';
import { toast } from 'svelte-sonner';

export type UseRoomSpotifyOAuthDeps = {
	setProviderLinkedForTransfer: (linked: boolean) => void;
	refreshProviderLinkStatus: (forProvider?: ProviderId) => Promise<boolean>;
	getTransferTargetUserId: () => string | undefined;
};

export function useRoomSpotifyOAuth(deps: UseRoomSpotifyOAuthDeps) {
	let spotifyOAuthQueryHandled = false;

	function reloadWithoutSpotifyQueryParams() {
		window.location.replace(buildPathWithoutSpotifyOAuthParams(window.location.href));
	}

	function showPendingSpotifyLinkToast() {
		const payload = readAndClearSpotifyLinkToast();
		if (!payload) return;
		if (payload.type === 'success') toast.success(payload.message);
		else if (payload.type === 'message') toast.message(payload.message);
		else toast.error(payload.message);
	}

	$effect(() => {
		if (!browser || spotifyOAuthQueryHandled) return;
		const params = page.url.searchParams;
		if (!params) return;

		if (!hasSpotifyOAuthQueryParams(params)) return;

		spotifyOAuthQueryHandled = true;

		const spotifyError = params.get('spotify_error');
		const spotifyLinked = params.get('spotify_linked') === 'true';

		if (spotifyError) {
			deps.setProviderLinkedForTransfer(false);
			writeSpotifyLinkToast({
				type: 'error',
				message: `Spotify link failed (${spotifyError}).${spotifyErrorHint(spotifyError)}`
			});
			reloadWithoutSpotifyQueryParams();
			return;
		}

		if (!spotifyLinked) {
			reloadWithoutSpotifyQueryParams();
			return;
		}

		void deps.refreshProviderLinkStatus('spotify').then((linked) => {
			const profileWarning = params.get('spotify_profile_warning');
			writeSpotifyLinkToast(toastPayloadAfterSpotifyLink(linked, profileWarning));
			reloadWithoutSpotifyQueryParams();
		});
	});

	$effect(() => {
		if (!browser) return;
		const transferTargetUserId = deps.getTransferTargetUserId();
		if (transferTargetUserId) {
			void deps.refreshProviderLinkStatus();
		}
	});

	return { showPendingSpotifyLinkToast };
}
