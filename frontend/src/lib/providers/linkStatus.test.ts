import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '$lib/api/client';
import { getAppleMusicLinkStatus, isProviderLinkedForUser } from './linkStatus';
import { isSpotifyLinkedForUser } from '$lib/session/spotifyLink';

vi.mock('$lib/api/client', () => ({
	apiClient: {
		getAppleMusicProfile: vi.fn()
	}
}));

vi.mock('$lib/session/spotifyLink', () => ({
	isSpotifyLinkedForUser: vi.fn()
}));

describe('linkStatus', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('delegates Spotify link checks', async () => {
		vi.mocked(isSpotifyLinkedForUser).mockResolvedValue(true);
		await expect(isProviderLinkedForUser('spotify', 'U_1')).resolves.toBe(true);
	});

	it('treats Apple Music as linked only when active and not needing relink', async () => {
		vi.mocked(apiClient.getAppleMusicProfile).mockResolvedValue({
			linked: true,
			storefront: 'us',
			display_name: 'Alice',
			needs_relink: false
		});
		await expect(getAppleMusicLinkStatus('U_1')).resolves.toEqual({
			linked: true,
			needsRelink: false
		});

		vi.mocked(apiClient.getAppleMusicProfile).mockResolvedValue({
			linked: true,
			storefront: 'us',
			display_name: 'Alice',
			needs_relink: true
		});
		await expect(getAppleMusicLinkStatus('U_1')).resolves.toEqual({
			linked: false,
			needsRelink: true
		});
	});
});
