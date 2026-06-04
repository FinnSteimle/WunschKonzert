export const HOST_PROMOTION_TOAST_KEY = 'wk_host_promotion_toast';

/**
 * Persist a toast across the deliberate page reload that runs when a browser
 * becomes the room host. The reload resets the music-provider SDK singletons
 * (Spotify Web Playback / Apple MusicKit), which keep stale device/auth state
 * across an in-page host handoff.
 */
export function writeHostPromotionToast(message: string): void {
	sessionStorage.setItem(HOST_PROMOTION_TOAST_KEY, message);
}

export function readAndClearHostPromotionToast(): string | null {
	const message = sessionStorage.getItem(HOST_PROMOTION_TOAST_KEY);
	if (!message) return null;
	sessionStorage.removeItem(HOST_PROMOTION_TOAST_KEY);
	return message;
}
