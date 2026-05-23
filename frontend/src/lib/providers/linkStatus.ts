import { apiClient } from '$lib/api/client';
import type { ProviderId } from '$lib/types/api';
import { isSpotifyLinkedForUser } from '$lib/session/spotifyLink';

export interface AppleMusicLinkStatus {
	linked: boolean;
	needsRelink: boolean;
}

/** True when the user has an active linked account for the given provider. */
export async function isProviderLinkedForUser(
	providerId: ProviderId,
	userId: string
): Promise<boolean> {
	if (providerId === 'spotify') {
		return isSpotifyLinkedForUser(userId);
	}
	const status = await getAppleMusicLinkStatus(userId);
	return status.linked;
}

export async function getAppleMusicLinkStatus(userId: string): Promise<AppleMusicLinkStatus> {
	const profile = await apiClient.getAppleMusicProfile(userId);
	return {
		linked: profile.linked && !profile.needs_relink,
		needsRelink: profile.linked && profile.needs_relink
	};
}
