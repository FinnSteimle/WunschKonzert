import { AppleMusicPlayer } from './appleMusicPlayer';
import { SpotifyPlayer, type SpotifyPlayerOptions } from './spotifyPlayer';
import type { MusicPlayer } from './types';
import type { ProviderId } from '$lib/types/api';

export type CreateMusicPlayerOptions = SpotifyPlayerOptions;

export function createMusicPlayer(
	providerId: ProviderId,
	userId: string,
	options?: CreateMusicPlayerOptions
): MusicPlayer {
	switch (providerId) {
		case 'spotify':
			return new SpotifyPlayer(userId, options);
		case 'apple-music':
			return new AppleMusicPlayer(userId);
		default:
			throw new Error(`Unsupported music provider: ${providerId}`);
	}
}
