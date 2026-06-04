import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '$lib/api/client';

vi.mock('$lib/api/client', () => ({
	apiClient: {
		getAppleMusicDeveloperToken: vi.fn(),
		getAppleMusicToken: vi.fn(),
		linkAppleMusic: vi.fn()
	}
}));

function createInstance(overrides: Partial<MusicKit.MusicKitInstance> = {}): MusicKit.MusicKitInstance {
	return {
		authorize: vi.fn().mockResolvedValue('mut-token'),
		musicUserToken: 'stored-mut',
		isAuthorized: true,
		play: vi.fn(),
		pause: vi.fn(),
		seekToTime: vi.fn(),
		currentPlaybackTime: 0,
		currentPlaybackDuration: 0,
		playbackState: 3,
		nowPlayingItem: null,
		setQueue: vi.fn(),
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		...overrides
	} as MusicKit.MusicKitInstance;
}

function installMusicKit(
	configureReturn: MusicKit.MusicKitInstance | Promise<MusicKit.MusicKitInstance>,
	getInstanceReturn?: MusicKit.MusicKitInstance
): MusicKit.MusicKitInstance {
	const instance =
		configureReturn instanceof Promise ? createInstance() : configureReturn;
	window.MusicKit = {
		configure: vi.fn().mockReturnValue(configureReturn),
		getInstance: vi.fn().mockReturnValue(getInstanceReturn ?? instance)
	};
	return instance;
}

describe('appleMusicAuth', () => {
	beforeEach(() => {
		vi.resetModules();
		vi.clearAllMocks();
		delete window.MusicKit;
		document
			.querySelectorAll('script[src*="musickit"]')
			.forEach((node) => node.remove());
	});

	async function loadModule() {
		return import('./appleMusicAuth');
	}

	it('configureMusicKit uses sync getInstance result', async () => {
		const instance = createInstance();
		installMusicKit(instance);
		const { configureMusicKit } = await loadModule();

		await expect(configureMusicKit({ developerToken: 'dev-token' })).resolves.toBe(instance);
		expect(window.MusicKit?.configure).toHaveBeenCalledWith(
			expect.objectContaining({
				developerToken: 'dev-token',
				suppressErrorDialog: true,
				app: { name: 'WunschKonzert', build: '1.0' }
			})
		);
	});

	it('configureMusicKit awaits promise returned from configure', async () => {
		const instance = createInstance();
		installMusicKit(Promise.resolve(instance));
		const { configureMusicKit } = await loadModule();

		await expect(
			configureMusicKit({ developerToken: 'dev-token', musicUserToken: 'mut' })
		).resolves.toBe(instance);
	});

	it('configureMusicKit throws when instance missing after configure', async () => {
		window.MusicKit = {
			configure: vi.fn().mockReturnValue(undefined),
			getInstance: vi.fn().mockReturnValue(undefined)
		};
		const { configureMusicKit } = await loadModule();

		await expect(configureMusicKit({ developerToken: 'dev-token' })).rejects.toThrow(
			'MusicKit instance not available after configure'
		);
	});

	it('loads MusicKit script and resolves on musickitloaded', async () => {
		const { configureMusicKit } = await loadModule();
		const pending = configureMusicKit({ developerToken: 'dev-token' });
		const instance = createInstance();
		window.MusicKit = {
			configure: vi.fn().mockReturnValue(instance),
			getInstance: vi.fn().mockReturnValue(instance)
		};
		document.dispatchEvent(new Event('musickitloaded'));
		await expect(pending).resolves.toBe(instance);
	});

	it('rejects when musickitloaded fires without MusicKit global', async () => {
		const { configureMusicKit } = await loadModule();
		const pending = configureMusicKit({ developerToken: 'dev-token' });
		document.dispatchEvent(new Event('musickitloaded'));
		await expect(pending).rejects.toThrow('MusicKit failed to initialize');
	});

	it('rejects when script fails to load', async () => {
		const { configureMusicKit } = await loadModule();
		const pending = configureMusicKit({ developerToken: 'dev-token' });
		const script = document.querySelector('script[src*="musickit"]') as HTMLScriptElement;
		script.onerror?.(new Event('error'));
		await expect(pending).rejects.toThrow('Failed to load Apple MusicKit');
	});

	it('linkAppleMusicAccount persists Music User Token', async () => {
		const instance = createInstance({
			authorize: vi.fn().mockResolvedValue('fresh-mut')
		});
		installMusicKit(instance);
		vi.mocked(apiClient.getAppleMusicDeveloperToken).mockResolvedValue({
			developer_token: 'dev-token'
		});
		vi.mocked(apiClient.linkAppleMusic).mockResolvedValue({
			storefront: 'us',
			display_name: 'Alice'
		});

		const { linkAppleMusicAccount } = await loadModule();
		await expect(linkAppleMusicAccount('U_1', 'Alice')).resolves.toEqual({
			storefront: 'us',
			display_name: 'Alice'
		});
		expect(apiClient.linkAppleMusic).toHaveBeenCalledWith({
			user_id: 'U_1',
			music_user_token: 'fresh-mut',
			display_name: 'Alice'
		});
	});

	it('linkAppleMusicAccount rejects when authorization is cancelled', async () => {
		const instance = createInstance({
			authorize: vi.fn().mockResolvedValue(undefined)
		});
		installMusicKit(instance);
		vi.mocked(apiClient.getAppleMusicDeveloperToken).mockResolvedValue({
			developer_token: 'dev-token'
		});

		const { linkAppleMusicAccount } = await loadModule();
		await expect(linkAppleMusicAccount('U_1', 'Alice')).rejects.toThrow(
			'Apple Music authorization was cancelled'
		);
	});

	it('configureMusicKitForUser restores stored token when available', async () => {
		const instance = createInstance();
		installMusicKit(instance);
		vi.mocked(apiClient.getAppleMusicDeveloperToken).mockResolvedValue({
			developer_token: 'dev-token'
		});
		vi.mocked(apiClient.getAppleMusicToken).mockResolvedValue({
			music_user_token: 'stored-mut'
		});

		const { configureMusicKitForUser } = await loadModule();
		await expect(configureMusicKitForUser('U_1')).resolves.toBe(instance);
		expect(window.MusicKit?.configure).toHaveBeenCalledWith(
			expect.objectContaining({ musicUserToken: 'stored-mut' })
		);
	});

	it('configureMusicKitForUser continues when stored token fetch fails', async () => {
		const instance = createInstance();
		installMusicKit(instance);
		vi.mocked(apiClient.getAppleMusicDeveloperToken).mockResolvedValue({
			developer_token: 'dev-token'
		});
		vi.mocked(apiClient.getAppleMusicToken).mockRejectedValue(new Error('not linked'));

		const { configureMusicKitForUser } = await loadModule();
		await expect(configureMusicKitForUser('U_1')).resolves.toBe(instance);
		expect(window.MusicKit?.configure).toHaveBeenCalledWith(
			expect.not.objectContaining({ musicUserToken: expect.anything() })
		);
	});
});
