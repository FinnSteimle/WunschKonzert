import { apiClient } from '$lib/api/client';

/** True when backend has a Spotify refresh token for this session user. */
export async function isSpotifyLinkedForUser(userId: string): Promise<boolean> {
	try {
		await apiClient.getSpotifyToken(userId);
		return true;
	} catch {
		return false;
	}
}
