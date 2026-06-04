import { browser } from '$app/environment';
import { roomStore } from '$lib/stores/room';
import type { RoomSocketClient } from '$lib/realtime/roomSocket';
import type { MusicPlayer, MusicPlayerState } from '$lib/playback/types';
import { isAutoplayBlockedError } from '$lib/playback/autoplayPolicy';
import { createMusicPlayer } from '$lib/playback/createMusicPlayer';
import type { ProviderId, QueueEntryDto } from '$lib/types/api';
import { get } from 'svelte/store';
import { isNeedsRelinkError } from '$lib/api/client';
import { toast } from 'svelte-sonner';

export type HostPlaybackDeps = {
	getSocketClient: () => RoomSocketClient | null;
	onSpotifyNeedsRelink?: () => void;
};

export function useHostPlayback(deps: HostPlaybackDeps) {
	let roomUi = $state(get(roomStore));

	$effect(() => {
		return roomStore.subscribe((value) => {
			roomUi = value;
		});
	});

	let musicPlayer = $state<MusicPlayer | null>(null);
	let sdkPlayerState = $state<MusicPlayerState | null>(null);
	let lastPlayedQueueEntryId = $state<string | null>(null);
	let advanceSent = false;
	let positionSyncInterval: ReturnType<typeof setInterval> | null = null;
	let playInitiatedEntryId = $state<string | null>(null);
	let hostPlaybackGestureUnlocked = $state(false);
	let playbackNeedsGesture = $state(false);
	let pendingHostPlay = $state<{
		queueEntryId: string;
		providerTrackId: string;
		positionMs: number;
	} | null>(null);
	let appleMusicDeferInitialPlay = $state(false);
	let suppressHostAutoSync = $state(false);
	let playbackBusy = $state(false);
	let lastKnownHostUserId = $state<string | undefined>(undefined);

	function roomProviderId(): ProviderId | undefined {
		const id = get(roomStore).roomState?.room.supportedProviderId;
		return id === 'spotify' || id === 'apple-music' ? id : undefined;
	}

	function requiresPlaybackGesture(): boolean {
		return roomProviderId() === 'apple-music' && !hostPlaybackGestureUnlocked;
	}

	function isAppleMusicHost(): boolean {
		return roomProviderId() === 'apple-music';
	}

	async function runHostPrepare(
		player: MusicPlayer,
		queueEntryId: string,
		providerTrackId: string,
		positionMs: number
	): Promise<void> {
		if (!player.prepare) {
			await runHostPlay(player, queueEntryId, providerTrackId, positionMs, true);
			return;
		}
		if (requiresPlaybackGesture()) {
			pendingHostPlay = { queueEntryId, providerTrackId, positionMs };
			playbackNeedsGesture = true;
			return;
		}
		playbackNeedsGesture = false;
		await player.prepare(providerTrackId, positionMs);
		lastPlayedQueueEntryId = queueEntryId;
		playInitiatedEntryId = queueEntryId;
		pendingHostPlay = null;
	}

	async function flushPendingHostPlayback(): Promise<void> {
		const player = musicPlayer;
		const pending = pendingHostPlay;
		if (!player || !sdkPlayerState?.isReady || !pending) return;

		const rs = get(roomStore).roomState;
		if (!rs || rs.playback?.currentQueueEntryId !== pending.queueEntryId) {
			pendingHostPlay = null;
			return;
		}

		lastPlayedQueueEntryId = pending.queueEntryId;
		playInitiatedEntryId = pending.queueEntryId;
		playbackNeedsGesture = false;

		try {
			if (isAppleMusicHost() && appleMusicDeferInitialPlay) {
				await runHostPrepare(
					player,
					pending.queueEntryId,
					pending.providerTrackId,
					pending.positionMs
				);
			} else {
				await player.play(pending.providerTrackId, pending.positionMs);
			}
			pendingHostPlay = null;
		} catch (err) {
			if (isAutoplayBlockedError(err)) {
				playbackNeedsGesture = true;
				lastPlayedQueueEntryId = null;
				playInitiatedEntryId = null;
				return;
			}
			console.error('[HostPlayer] play failed:', err);
			lastPlayedQueueEntryId = null;
			playInitiatedEntryId = null;
			pendingHostPlay = null;
		}
	}

	function unlockHostPlayback(): void {
		hostPlaybackGestureUnlocked = true;
		void flushPendingHostPlayback();
	}

	async function runHostPlay(
		player: MusicPlayer,
		queueEntryId: string,
		providerTrackId: string,
		positionMs: number,
		forcePlay = false
	): Promise<void> {
		if (!forcePlay && isAppleMusicHost() && appleMusicDeferInitialPlay) {
			await runHostPrepare(player, queueEntryId, providerTrackId, positionMs);
			return;
		}

		if (requiresPlaybackGesture()) {
			pendingHostPlay = { queueEntryId, providerTrackId, positionMs };
			playbackNeedsGesture = true;
			return;
		}

		playbackNeedsGesture = false;
		try {
			await player.play(providerTrackId, positionMs);
			lastPlayedQueueEntryId = queueEntryId;
			playInitiatedEntryId = queueEntryId;
			pendingHostPlay = null;
		} catch (err) {
			if (isAutoplayBlockedError(err)) {
				pendingHostPlay = { queueEntryId, providerTrackId, positionMs };
				playbackNeedsGesture = true;
				lastPlayedQueueEntryId = null;
				playInitiatedEntryId = null;
				return;
			}
			throw err;
		}
	}

	async function runHostResume(player: MusicPlayer): Promise<void> {
		if (playbackNeedsGesture || requiresPlaybackGesture()) return;
		try {
			await player.resume();
		} catch (err) {
			if (isAutoplayBlockedError(err)) {
				playbackNeedsGesture = true;
				return;
			}
			throw err;
		}
	}

	async function handlePlayback(action: 'pause' | 'resume', sessionUserId: string | undefined) {
		const rs = get(roomStore).roomState;
		const socketClient = deps.getSocketClient();
		if (!sessionUserId || !socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return;
		}
		hostPlaybackGestureUnlocked = true;
		playbackNeedsGesture = false;
		suppressHostAutoSync = true;
		playbackBusy = true;
		try {
			if (action === 'resume' && isAppleMusicHost()) {
				appleMusicDeferInitialPlay = false;
			}
			const currentEntryId = rs?.playback?.currentQueueEntryId;
			const currentEntry = rs?.queue.find((e) => e.queueEntryId === currentEntryId);
			const serverProviderTrackId = currentEntry?.track.providerTrackId;

			const isCorrectEntry =
				currentEntryId === lastPlayedQueueEntryId && currentEntryId !== playInitiatedEntryId;
			let localTrackId = musicPlayer?.getLastTrackId();
			if (isCorrectEntry && localTrackId && serverProviderTrackId?.includes(localTrackId)) {
				// Tracks and entry match
			} else {
				localTrackId = null;
			}

			if (musicPlayer) {
				if (action === 'pause') {
					await musicPlayer.pause();
				} else if (localTrackId) {
					await runHostResume(musicPlayer);
				} else if (serverProviderTrackId && currentEntryId) {
					await runHostPlay(
						musicPlayer,
						currentEntryId,
						serverProviderTrackId,
						rs?.playback?.positionMs ?? 0,
						true
					);
				}
			}

			const currentPos =
				localTrackId && musicPlayer
					? await musicPlayer.getPositionMs()
					: localTrackId && sdkPlayerState
						? sdkPlayerState.positionMs
						: undefined;

			const sent = await socketClient.setPlayback(
				sessionUserId,
				action,
				currentPos,
				currentEntryId ?? undefined
			);
			if (!sent) {
				throw new Error('Playback command failed');
			}
		} catch (err) {
			if (!isNeedsRelinkError(err)) {
				toast.error(err instanceof Error ? err.message : 'Playback command failed');
			}
		} finally {
			playbackBusy = false;
			setTimeout(() => {
				suppressHostAutoSync = false;
			}, 600);
		}
	}

	function initMusicPlayer(userId: string, providerId: ProviderId): void {
		appleMusicDeferInitialPlay = providerId === 'apple-music';
		hostPlaybackGestureUnlocked = providerId !== 'apple-music';
		const player = createMusicPlayer(providerId, userId, {
			onNeedsRelink: providerId === 'spotify' ? deps.onSpotifyNeedsRelink : undefined
		});
		player.onStateChange((s) => {
			sdkPlayerState = s;

			if (s.trackEnded && !advanceSent) {
				advanceSent = true;
				const pos = Math.round(s.positionMs ?? 0);
				const rs = get(roomStore).roomState;
				const currentEntryId = rs?.playback?.currentQueueEntryId;

				const isCorrectEntry =
					currentEntryId === lastPlayedQueueEntryId && currentEntryId !== playInitiatedEntryId;

				deps.getSocketClient()?.send({
					type: 'playback',
					user_id: userId,
					action: 'advance',
					position_ms: isCorrectEntry ? pos : 0
				});

				deps.getSocketClient()?.send({
					type: 'position_sync',
					user_id: userId,
					position_ms: isCorrectEntry ? pos : 0,
					queue_entry_id: currentEntryId
				});
			}
		});
		musicPlayer = player;
		player.connect().catch((err) => {
			console.error('[SpotifyPlayer] connect failed:', err);
		});

		positionSyncInterval = setInterval(() => {
			const socketClient = deps.getSocketClient();
			if (!socketClient?.isConnected() || !sdkPlayerState?.isPlaying) return;

			const rs = get(roomStore).roomState;
			const currentEntryId = rs?.playback?.currentQueueEntryId;
			const currentEntry = rs?.queue.find((e) => e.queueEntryId === currentEntryId);
			const serverProviderTrackId = currentEntry?.track.providerTrackId;
			const localTrackId = musicPlayer?.getLastTrackId();

			const isCorrectEntry =
				currentEntryId === lastPlayedQueueEntryId && currentEntryId !== playInitiatedEntryId;
			if (isCorrectEntry && localTrackId && serverProviderTrackId?.includes(localTrackId)) {
				musicPlayer?.getPositionMs().then((pos) => {
					socketClient.send({
						type: 'position_sync',
						user_id: userId,
						position_ms: Math.round(pos),
						queue_entry_id: currentEntryId
					});
				});
			}
		}, 5000);
	}

	function teardownHostPlayback(): void {
		if (positionSyncInterval) {
			clearInterval(positionSyncInterval);
			positionSyncInterval = null;
		}
		musicPlayer?.disconnect();
		musicPlayer = null;
		sdkPlayerState = null;
		hostPlaybackGestureUnlocked = false;
		playbackNeedsGesture = false;
		pendingHostPlay = null;
		appleMusicDeferInitialPlay = false;
		suppressHostAutoSync = false;
		lastPlayedQueueEntryId = null;
		playInitiatedEntryId = null;
	}

	function maybeInitHostPlayer(
		sessionUserId: string | undefined,
		hostUserId: string | undefined,
		providerId: string | undefined
	): void {
		if (
			!musicPlayer &&
			sessionUserId &&
			hostUserId === sessionUserId &&
			(providerId === 'spotify' || providerId === 'apple-music')
		) {
			initMusicPlayer(sessionUserId, providerId);
		}
	}

	$effect(() => {
		if (!browser) return;
		const onGesture = () => {
			if (!hostPlaybackGestureUnlocked) {
				hostPlaybackGestureUnlocked = true;
				void flushPendingHostPlayback();
			}
		};
		document.addEventListener('pointerdown', onGesture, { capture: true });
		document.addEventListener('keydown', onGesture, { capture: true });
		return () => {
			document.removeEventListener('pointerdown', onGesture, { capture: true });
			document.removeEventListener('keydown', onGesture, { capture: true });
		};
	});

	$effect(() => {
		if (!browser) return;

		const player = musicPlayer;
		const ready = sdkPlayerState?.isReady;
		const rs = roomUi.roomState;

		if (!player || !ready || !rs) return;

		const queueEntryId = rs.playback?.currentQueueEntryId ?? null;
		const playbackState = rs.playback?.state;

		if (!queueEntryId || playbackState !== 'playing') {
			return;
		}

		if (queueEntryId === lastPlayedQueueEntryId) return;

		const entry = rs.queue.find((e: QueueEntryDto) => e.queueEntryId === queueEntryId);
		if (!entry) return;

		lastPlayedQueueEntryId = queueEntryId;
		playInitiatedEntryId = queueEntryId;
		advanceSent = false;

		setTimeout(() => {
			if (playInitiatedEntryId === queueEntryId) {
				playInitiatedEntryId = null;
			}
		}, 10000);

		const resumePos = rs.playback?.positionMs ?? 0;
		void runHostPlay(player, queueEntryId, entry.track.providerTrackId, resumePos).catch((err) => {
			if (isAutoplayBlockedError(err) || isNeedsRelinkError(err)) return;
			console.error('[HostPlayer] play failed:', err);
			lastPlayedQueueEntryId = null;
			playInitiatedEntryId = null;
		});
	});

	$effect(() => {
		if (!browser || !musicPlayer || !sdkPlayerState?.isReady) return;
		const rs = roomUi.roomState;
		if (!rs?.playback) return;

		const serverPlaying = rs.playback.state === 'playing';
		const localPlaying = sdkPlayerState.isPlaying;

		if (localPlaying && playInitiatedEntryId === rs.playback.currentQueueEntryId) {
			const currentEntry = rs.queue.find(
				(e: QueueEntryDto) => e.queueEntryId === playInitiatedEntryId
			);
			const trackMatch =
				currentEntry &&
				sdkPlayerState.trackId &&
				currentEntry.track.providerTrackId.includes(sdkPlayerState.trackId);

			const serverPos = rs.playback.positionMs ?? 0;
			const isSynced =
				trackMatch &&
				(sdkPlayerState.positionMs < 2000 ||
					Math.abs(sdkPlayerState.positionMs - serverPos) < 5000);

			if (isSynced) {
				playInitiatedEntryId = null;
			}
		}

		if (serverPlaying && !localPlaying) {
			if (suppressHostAutoSync) return;
			if (isAppleMusicHost() && appleMusicDeferInitialPlay) return;
			if (
				rs.playback.currentQueueEntryId === lastPlayedQueueEntryId &&
				playInitiatedEntryId !== rs.playback.currentQueueEntryId
			) {
				void runHostResume(musicPlayer).catch((err) => {
					if (isAutoplayBlockedError(err)) return;
					console.error('[HostPlayer] sync resume failed:', err);
				});
			}
		} else if (!serverPlaying && localPlaying) {
			musicPlayer.pause().catch((err) => console.error('[SpotifyPlayer] sync pause failed:', err));
		}
	});

	return {
		get musicPlayer() {
			return musicPlayer;
		},
		get sdkPlayerState() {
			return sdkPlayerState;
		},
		get lastPlayedQueueEntryId() {
			return lastPlayedQueueEntryId;
		},
		get playInitiatedEntryId() {
			return playInitiatedEntryId;
		},
		get playbackNeedsGesture() {
			return playbackNeedsGesture;
		},
		get appleMusicDeferInitialPlay() {
			return appleMusicDeferInitialPlay;
		},
		get playbackBusy() {
			return playbackBusy;
		},
		handlePlayback,
		unlockHostPlayback,
		initMusicPlayer,
		teardownHostPlayback,
		maybeInitHostPlayer,
		getLastKnownHostUserId(): string | undefined {
			return lastKnownHostUserId;
		},
		syncHostRole(sessionUserId: string | undefined): void {
			const rs = get(roomStore).roomState;
			if (!rs) return;

			const hostId = rs.host.userId;
			const wasHost = lastKnownHostUserId === sessionUserId;
			const isHostNow = hostId === sessionUserId;

			if (wasHost && !isHostNow && musicPlayer) {
				teardownHostPlayback();
			}

			lastKnownHostUserId = hostId;
		}
	};
}
