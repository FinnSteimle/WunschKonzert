import { AppleMusicPlayer } from './appleMusicPlayer';
import { SpotifyPlayer } from './spotifyPlayer';
import type { MusicPlayer } from './types';
import type { ProviderId } from '$lib/types/api';

export function createMusicPlayer(providerId: ProviderId, userId: string): MusicPlayer {
	switch (providerId) {
		case 'spotify':
			return new SpotifyPlayer(userId);
		case 'apple-music':
			return new AppleMusicPlayer(userId);
		default:
			throw new Error(`Unsupported music provider: ${providerId}`);
	}
}
