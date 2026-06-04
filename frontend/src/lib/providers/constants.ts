import type { ProviderId } from '$lib/types/api';

export const SUPPORTED_PROVIDERS: ProviderId[] = ['spotify', 'apple-music'];

export const PROVIDER_LABELS: Record<ProviderId, string> = {
	spotify: 'Spotify',
	'apple-music': 'Apple Music'
};

export function providerLabel(providerId: string | undefined): string {
	if (providerId === 'spotify' || providerId === 'apple-music') {
		return PROVIDER_LABELS[providerId];
	}
	return 'music';
}

export function isSupportedProviderId(value: string): value is ProviderId {
	return SUPPORTED_PROVIDERS.includes(value as ProviderId);
}
