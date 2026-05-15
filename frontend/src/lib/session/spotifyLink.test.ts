import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '$lib/api/client';
import { isSpotifyLinkedForUser } from './spotifyLink';

vi.mock('$lib/api/client', () => ({
	apiClient: {
		getSpotifyToken: vi.fn()
	}
}));

describe('isSpotifyLinkedForUser', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('returns true when token endpoint succeeds', async () => {
		vi.mocked(apiClient.getSpotifyToken).mockResolvedValue({ access_token: 'tok' });
		await expect(isSpotifyLinkedForUser('U_1')).resolves.toBe(true);
	});

	it('returns false when token endpoint fails', async () => {
		vi.mocked(apiClient.getSpotifyToken).mockRejectedValue(new Error('404'));
		await expect(isSpotifyLinkedForUser('U_1')).resolves.toBe(false);
	});
});
