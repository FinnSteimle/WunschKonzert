<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { apiClient } from '$lib/api/client';
	import {
		roomStore,
		getCurrentSong,
		queueWithoutCurrent,
		activeQueuedTrackIds,
		countActiveRoomMembers,
		clientReplayVoteFromPlayingEntry,
		replayMajorityThreshold,
		displayNameForUser
	} from '$lib/stores/room';
	import { RoomSocketClient } from '$lib/realtime/roomSocket';
	import {
		generateRandomDisplayName,
		getOrCreateSessionUser,
		saveSessionDisplayName
	} from '$lib/session/userSession';
	import {
		isJoinFailureForRemovedRoom,
		recordRecentRoom,
		removeRecentRoom
	} from '$lib/session/recentRooms';
	import type { TrackDto, VoteRequest } from '$lib/types/api';
	import type { MusicPlayer, MusicPlayerState } from '$lib/playback/types';
	import { isAutoplayBlockedError } from '$lib/playback/autoplayPolicy';
	import { createMusicPlayer } from '$lib/playback/createMusicPlayer';
	import { linkAppleMusicAccount } from '$lib/providers/appleMusicAuth';
	import { providerLabel } from '$lib/providers/constants';
	import { isProviderLinkedForUser } from '$lib/providers/linkStatus';
	import type { ProviderId } from '$lib/types/api';
	import { Badge } from '$lib/components/ui/badge';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import CurrentSongCard from '$lib/components/room/playback/CurrentSongCard.svelte';
	import PlaybackProgress from '$lib/components/room/playback/PlaybackProgress.svelte';
	import PlaybackControls from '$lib/components/room/playback/PlaybackControls.svelte';
	import QueueList from '$lib/components/room/queue/QueueList.svelte';
	import SongSearchPanel from '$lib/components/room/queue/SongSearchPanel.svelte';
	import UserList from '$lib/components/room/participants/UserList.svelte';
	import HostTransferPanel from '$lib/components/room/host-transfer/HostTransferPanel.svelte';
	import SystemMessagesList from '$lib/components/room/host-transfer/SystemMessagesList.svelte';
	import LeaveRoomButton from '$lib/components/room/actions/LeaveRoomButton.svelte';
	import DeleteRoomButton from '$lib/components/room/actions/DeleteRoomButton.svelte';
	import InvitePanelDialog from '$lib/components/room/invite/InvitePanelDialog.svelte';
	import LoadingState from '$lib/components/room/states/LoadingState.svelte';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';
	import SongHistoryModal from '$lib/components/room/history/SongHistoryModal.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import DisplayNameInput from '$lib/components/room/forms/DisplayNameInput.svelte';
	import { toast } from 'svelte-sonner';
	import { parseRoomSlug } from '$lib/room/slug';
	import {
		buildPathWithoutSpotifyOAuthParams,
		hasSpotifyOAuthQueryParams,
		readAndClearSpotifyLinkToast,
		spotifyErrorHint,
		toastPayloadAfterSpotifyLink,
		writeSpotifyLinkToast
	} from '$lib/room/spotifyOAuthReturn';
	import { get } from 'svelte/store';

	let sessionUser = $state<{ userId: string; displayName: string } | null>(
		browser ? getOrCreateSessionUser() : null
	);
	let recordedRecentThisMount = false;
	let socketClient = $state<RoomSocketClient | null>(null);
	let voteBusyId = $state<string | null>(null);
	let playbackBusy = $state(false);
	let renameDisplayName = $state('');
	let renameBusy = $state(false);
	let renameDialogOpen = $state(false);
	let hostTransferBusyUserId = $state<string | null>(null);
	let hostTransferActionBusy = $state(false);
	let hostTransferLinkBusy = $state(false);
	let providerLinkedForTransfer = $state(false);

	// Host music SDK playback
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
	/** Apple Music: first track load stays paused until host presses Resume. */
	let appleMusicDeferInitialPlay = $state(false);
	let suppressHostAutoSync = $state(false);

	/** Direct link /room/{code}: ask for name before calling join API. */
	let linkJoinCode = $state<string | null>(null);
	let linkJoinDisplayName = $state('');
	let linkJoinBusy = $state(false);
	let linkJoinError = $state<string | null>(null);
	const linkJoinLifecycle = {
		cancelled: false,
		endSession: undefined as (() => void) | undefined
	};

	async function handleVote(queueEntryId: string, vote: VoteRequest['vote_type']) {
		const uid = sessionUser?.userId;
		if (!uid || !socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return;
		}
		voteBusyId = queueEntryId;
		try {
			const sent = await socketClient.sendVote(queueEntryId, uid, vote);
			if (!sent) {
				throw new Error('Vote failed');
			}
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Vote failed');
		} finally {
			voteBusyId = null;
		}
	}

	async function handleRemove(queueEntryId: string) {
		const uid = sessionUser?.userId;
		if (!uid || !socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return;
		}
		voteBusyId = queueEntryId;
		try {
			const sent = socketClient.removeQueueEntry(queueEntryId, uid);
			if (!sent) {
				throw new Error('Remove failed');
			}
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Remove failed');
		} finally {
			voteBusyId = null;
		}
	}

	async function handlePlayback(action: 'pause' | 'resume') {
		const uid = sessionUser?.userId;
		const rs = get(roomStore).roomState;
		if (!uid || !socketClient || !socketClient.isConnected()) {
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

			// Strictly check if local player is on the same queue entry as the server
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
				uid,
				action,
				currentPos,
				currentEntryId ?? undefined
			);
			if (!sent) {
				throw new Error('Playback command failed');
			}
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Playback command failed');
		} finally {
			playbackBusy = false;
			setTimeout(() => {
				suppressHostAutoSync = false;
			}, 600);
		}
	}

	function saveDisplayNameChange(): boolean {
		const uid = sessionUser?.userId;
		const trimmed = renameDisplayName.trim();
		if (!uid || !socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return false;
		}
		if (!trimmed) {
			toast.error('Please enter your display name.');
			return false;
		}
		if (trimmed.length > 60) {
			toast.error('Display name must be 60 characters or fewer.');
			return false;
		}
		if (trimmed === sessionUser?.displayName) {
			return true;
		}

		renameBusy = true;
		try {
			const sent = socketClient.renameDisplayName(uid, trimmed);
			if (!sent) {
				throw new Error('Rename failed');
			}
			saveSessionDisplayName(trimmed);
			if (sessionUser) {
				sessionUser = { ...sessionUser, displayName: trimmed };
			}
			toast.success('Display name updated');
			return true;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Rename failed');
			return false;
		} finally {
			renameBusy = false;
		}
	}

	function openRenameDialog() {
		renameDisplayName = sessionUser?.displayName ?? '';
		renameDialogOpen = true;
	}

	function handleRenameSave() {
		const saved = saveDisplayNameChange();
		if (saved) {
			renameDialogOpen = false;
		}
	}

	function handleRenameSubmit(event: Event) {
		event.preventDefault();
		handleRenameSave();
	}

	async function handleOfferHostTransfer(targetUserId: string) {
		const uid = sessionUser?.userId;
		const rs = get(roomStore).roomState;
		if (!uid || !rs || rs.host.userId !== uid) return;
		if (rs.transfer) {
			toast.error('A host transfer is already pending.');
			return;
		}
		if (!socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return;
		}
		hostTransferBusyUserId = targetUserId;
		try {
			const sent = socketClient.initiateHostTransfer(uid, targetUserId);
			if (!sent) throw new Error('Could not send host transfer invite');
			toast.message('Host invite sent to ' + displayNameForUser(rs, targetUserId) + '.');
		} catch (err) {
			hostTransferBusyUserId = null;
			toast.error(err instanceof Error ? err.message : 'Host transfer failed');
		}
	}

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

	async function refreshProviderLinkStatus(forProvider?: ProviderId): Promise<boolean> {
		const uid = sessionUser?.userId;
		const providerId = forProvider ?? roomProviderId();
		if (!uid || !providerId) {
			providerLinkedForTransfer = false;
			return false;
		}
		const linked = await isProviderLinkedForUser(providerId, uid);
		providerLinkedForTransfer = linked;
		return linked;
	}

	async function handleAcceptHostTransfer() {
		const uid = sessionUser?.userId;
		const rs = get(roomStore).roomState;
		const transfer = rs?.transfer;
		if (!uid || !transfer || transfer.toUserId !== uid) return;
		if (!socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return;
		}
		hostTransferActionBusy = true;
		try {
			const linked = await refreshProviderLinkStatus();
			const providerId = roomProviderId();
			if (!linked) {
				const label = providerLabel(providerId);
				toast.error(
					`${label} is not linked for this browser session. Use “Link ${label} account” below, then accept again.`
				);
				return;
			}
			const sent = socketClient.acceptHostTransfer(uid, transfer.transferId);
			if (!sent) throw new Error('Could not accept host transfer');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not accept host transfer');
		} finally {
			hostTransferActionBusy = false;
		}
	}

	async function handleRejectHostTransfer() {
		const uid = sessionUser?.userId;
		const rs = get(roomStore).roomState;
		const transfer = rs?.transfer;
		if (!uid || !transfer || transfer.toUserId !== uid) return;
		if (!socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return;
		}
		hostTransferActionBusy = true;
		try {
			const sent = socketClient.rejectHostTransfer(uid, transfer.transferId);
			if (!sent) throw new Error('Could not decline host transfer');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not decline host transfer');
		} finally {
			hostTransferActionBusy = false;
		}
	}

	async function linkProviderForHostTransfer() {
		const uid = sessionUser?.userId;
		const providerId = roomProviderId();
		if (!uid || !providerId) return;
		hostTransferLinkBusy = true;
		try {
			if (providerId === 'spotify') {
				const returnTo = `${window.location.origin}${window.location.pathname}`;
				const { auth_url } = await apiClient.getSpotifyLoginUrl(uid, returnTo, {
					forceConsent: true
				});
				window.location.href = auth_url;
				return;
			}
			const displayName = sessionUser?.displayName?.trim();
			if (!displayName) {
				toast.error('Set your display name before linking Apple Music.');
				return;
			}
			await linkAppleMusicAccount(uid, displayName);
			await refreshProviderLinkStatus();
			toast.success('Apple Music account linked');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not link music account');
		} finally {
			hostTransferLinkBusy = false;
		}
	}

	$effect(() => {
		if (!browser) return;
		const rs = $roomStore.roomState;
		const su = sessionUser;
		if (recordedRecentThisMount || !rs || !su) return;
		recordedRecentThisMount = true;
		recordRecentRoom({
			joinCode: rs.room.joinCode,
			name: rs.room.name,
			isHost: rs.host.userId === su.userId
		});
	});

	const REPLAY_SUCCESS_EVENTS = new Set(['replay_scheduled', 'playback_replayed']);
	const HOST_TRANSFER_EVENTS = new Set([
		'host_transfer_initiated',
		'host_transfer_rejected',
		'host_transfer_completed'
	]);
	let lastReplayEventSignature = $state<string | undefined>(undefined);
	let lastHostTransferEventSignature = $state<string | undefined>(undefined);
	let lastKnownHostUserId = $state<string | undefined>(undefined);
	let spotifyOAuthQueryHandled = false;

	function reloadWithoutSpotifyQueryParams() {
		window.location.replace(buildPathWithoutSpotifyOAuthParams(window.location.href));
	}

	$effect(() => {
		if (!browser) return;
		const ev = $roomStore.roomState?.lastEvent;
		const sig = ev ? `${ev.type}:${ev.at}` : '';
		const prev = lastReplayEventSignature;
		lastReplayEventSignature = sig;
		if (ev && REPLAY_SUCCESS_EVENTS.has(ev.type) && prev !== undefined && sig !== prev) {
			toast.success(
				'The group voted to replay this track. It has been added to the top of the queue.'
			);
		}
	});

	$effect(() => {
		if (!browser) return;
		const rs = $roomStore.roomState;
		const su = sessionUser;
		const ev = rs?.lastEvent;
		const sig = ev ? `${ev.type}:${ev.at}` : '';
		const prev = lastHostTransferEventSignature;
		const prevHostId = lastKnownHostUserId;

		if (rs?.transfer) {
			hostTransferBusyUserId = null;
		}

		if (ev && HOST_TRANSFER_EVENTS.has(ev.type) && prev !== undefined && sig !== prev && su && rs) {
			if (ev.type === 'host_transfer_completed') {
				if (rs.host.userId === su.userId && prevHostId !== su.userId) {
					toast.success('You are now the room host.');
				} else if (prevHostId === su.userId && rs.host.userId !== su.userId) {
					toast.message(
						'Host role transferred to ' + displayNameForUser(rs, rs.host.userId) + '.'
					);
				}
			} else if (ev.type === 'host_transfer_rejected' && rs.host.userId === su.userId) {
				toast.message('Host transfer was declined.');
			}
		}

		lastHostTransferEventSignature = sig;
	});

	$effect(() => {
		if (!browser) return;
		const rs = $roomStore.roomState;
		const su = sessionUser;
		if (!rs || !su) return;

		const hostId = rs.host.userId;
		const wasHost = lastKnownHostUserId === su.userId;
		const isHostNow = hostId === su.userId;

		if (wasHost && !isHostNow && musicPlayer) {
			if (positionSyncInterval) {
				clearInterval(positionSyncInterval);
				positionSyncInterval = null;
			}
			musicPlayer.disconnect();
			musicPlayer = null;
			sdkPlayerState = null;
			lastPlayedQueueEntryId = null;
			playInitiatedEntryId = null;
		}

		lastKnownHostUserId = hostId;
	});

	$effect(() => {
		if (!browser || spotifyOAuthQueryHandled) return;
		const params = page.url.searchParams;
		if (!params) return;

		if (!hasSpotifyOAuthQueryParams(params)) return;

		spotifyOAuthQueryHandled = true;

		const spotifyError = params.get('spotify_error');
		const spotifyLinked = params.get('spotify_linked') === 'true';

		if (spotifyError) {
			providerLinkedForTransfer = false;
			writeSpotifyLinkToast({
				type: 'error',
				message: `Spotify link failed (${spotifyError}).${spotifyErrorHint(spotifyError)}`
			});
			reloadWithoutSpotifyQueryParams();
			return;
		}

		if (!spotifyLinked) {
			reloadWithoutSpotifyQueryParams();
			return;
		}

		void refreshProviderLinkStatus('spotify').then((linked) => {
			const profileWarning = params.get('spotify_profile_warning');
			writeSpotifyLinkToast(
				toastPayloadAfterSpotifyLink(linked, profileWarning)
			);
			reloadWithoutSpotifyQueryParams();
		});
	});

	$effect(() => {
		if (!browser || !sessionUser) return;
		const transfer = $roomStore.roomState?.transfer;
		if (transfer?.toUserId === sessionUser.userId) {
			void refreshProviderLinkStatus();
		}
	});

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

	// When the server's current track changes (or the SDK becomes ready), play it.
	$effect(() => {
		if (!browser) return;

		const player = musicPlayer;
		const ready = sdkPlayerState?.isReady;
		const rs = $roomStore.roomState;

		// Wait until player and SDK are ready
		if (!player || !ready || !rs) return;

		const queueEntryId = rs.playback?.currentQueueEntryId ?? null;
		const playbackState = rs.playback?.state;

		// ONLY initiate a new 'play' command if the server explicitly says we are 'playing'.
		// This prevents accidental auto-play on first song addition or during state transitions.
		if (!queueEntryId || playbackState !== 'playing') {
			return;
		}

		if (queueEntryId === lastPlayedQueueEntryId) return;

		const entry = rs.queue.find((e) => e.queueEntryId === queueEntryId);
		if (!entry) return;

		lastPlayedQueueEntryId = queueEntryId;
		playInitiatedEntryId = queueEntryId;
		advanceSent = false;

		// Safety timeout: never stay in playInitiated quarantine for more than 10s
		setTimeout(() => {
			if (playInitiatedEntryId === queueEntryId) {
				playInitiatedEntryId = null;
			}
		}, 10000);

		const resumePos = rs.playback?.positionMs ?? 0;
		void runHostPlay(player, queueEntryId, entry.track.providerTrackId, resumePos).catch((err) => {
			if (isAutoplayBlockedError(err)) return;
			console.error('[HostPlayer] play failed:', err);
			lastPlayedQueueEntryId = null;
			playInitiatedEntryId = null;
		});
	});

	// Sync local player pause/resume state with server state (handles multi-tab host sync)
	$effect(() => {
		if (!browser || !musicPlayer || !sdkPlayerState?.isReady) return;
		const rs = $roomStore.roomState;
		if (!rs?.playback) return;

		const serverPlaying = rs.playback.state === 'playing';
		const localPlaying = sdkPlayerState.isPlaying;

		// Reset playInitiated only once the local player confirms it is playing the CORRECT track
		// AND the position has actually reset (to handle the same-track-re-add jump).
		if (localPlaying && playInitiatedEntryId === rs.playback.currentQueueEntryId) {
			const currentEntry = rs.queue.find((e) => e.queueEntryId === playInitiatedEntryId);
			const trackMatch =
				currentEntry &&
				sdkPlayerState.trackId &&
				currentEntry.track.providerTrackId.includes(sdkPlayerState.trackId);

			// We wait for track match AND either a small position (fresh play) or a large one (syncing to middle).
			// This covers both new songs and newly joining hosts syncing to a song already in progress.
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
			// Only resume if we are already on the correct track AND we didn't just initiate a play
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
			// Aggressively pause if the server says we should be paused/stopped
			musicPlayer.pause().catch((err) => console.error('[SpotifyPlayer] sync pause failed:', err));
		}
	});

	async function handleAddTrack(track: TrackDto) {
		const uid = sessionUser?.userId;
		if (!uid || !socketClient || !socketClient.isConnected()) {
			throw new Error('Not connected to room');
		}

		// Avoid pointless backend 409 errors and show a nicer UX.
		const currentState = get(roomStore).roomState;
		if (
			currentState?.queue.some(
				(entry) => entry.track.trackId === track.trackId && entry.status !== 'played'
			)
		) {
			throw new Error('Song is already in the queue');
		}

		try {
			const sent = await socketClient.addToQueue(track, uid);
			if (!sent) {
				throw new Error('Could not add song');
			}
		} catch (err) {
			throw new Error(err instanceof Error ? err.message : 'Could not add song');
		}
	}

	function initMusicPlayer(userId: string, providerId: ProviderId): void {
		appleMusicDeferInitialPlay = providerId === 'apple-music';
		hostPlaybackGestureUnlocked = providerId !== 'apple-music';
		const player = createMusicPlayer(providerId, userId);
		player.onStateChange((s) => {
			sdkPlayerState = s;

			if (s.trackEnded && !advanceSent) {
				advanceSent = true;
				const pos = Math.round(s.positionMs ?? 0);
				const rs = get(roomStore).roomState;
				const currentEntryId = rs?.playback?.currentQueueEntryId;

				// Only send the position if we're actually still on that entry and not initiating a new play
				const isCorrectEntry =
					currentEntryId === lastPlayedQueueEntryId && currentEntryId !== playInitiatedEntryId;

				// Send advance with the host's last known position to help the server
				// compute an accurate start time for the next track.
				socketClient?.send({
					type: 'playback',
					user_id: userId,
					action: 'advance',
					position_ms: isCorrectEntry ? pos : 0
				});

				// Also send an immediate position_sync so the server has the latest
				// authoritative position (helps newly joining clients sync).
				socketClient?.send({
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
			if (!socketClient?.isConnected() || !sdkPlayerState?.isPlaying) return;

			const rs = get(roomStore).roomState;
			const currentEntryId = rs?.playback?.currentQueueEntryId;
			const currentEntry = rs?.queue.find((e) => e.queueEntryId === currentEntryId);
			const serverProviderTrackId = currentEntry?.track.providerTrackId;
			const localTrackId = musicPlayer?.getLastTrackId();

			// Only sync if local track and queue entry match server and not initiating a new play
			const isCorrectEntry =
				currentEntryId === lastPlayedQueueEntryId && currentEntryId !== playInitiatedEntryId;
			if (isCorrectEntry && localTrackId && serverProviderTrackId?.includes(localTrackId)) {
				musicPlayer?.getPositionMs().then((pos) => {
					socketClient?.send({
						type: 'position_sync',
						user_id: userId,
						position_ms: Math.round(pos),
						queue_entry_id: currentEntryId
					});
				});
			}
		}, 5000);
	}

	function beginRoomSession(roomId: string): () => void {
		roomStore.reset();
		roomStore.setLoading(true);

		let roomDeletedRedirectDone = false;
		const unsubDeleted = roomStore.subscribe((ui) => {
			if (roomDeletedRedirectDone) return;
			if (ui.roomState?.room.status === 'deleted') {
				roomDeletedRedirectDone = true;
				removeRecentRoom(ui.roomState.room.joinCode);
				if (sessionUser && ui.roomState.host.userId !== sessionUser.userId) {
					toast.message('Room ended by host');
				}
				void goto(resolve('/'));
			}

			// Initialize the host player once we know this user is the host.
			const providerId = ui.roomState?.room.supportedProviderId;
			if (
				!musicPlayer &&
				sessionUser &&
				ui.roomState?.host.userId === sessionUser.userId &&
				(providerId === 'spotify' || providerId === 'apple-music')
			) {
				initMusicPlayer(sessionUser.userId, providerId);
			}
		});

		const socket = new RoomSocketClient(
			roomId,
			{
				onState: (s) => roomStore.setRoomState(s),
				onError: (m) => {
					toast.error(m);
					roomStore.setError(m);
				},
				onConnectionChange: (c) => roomStore.setConnected(c)
			},
			sessionUser?.userId
		);
		socketClient = socket;
		socket.connect();

		return () => {
			unsubDeleted();
			socket.disconnect();
			socketClient = null;
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
			roomStore.reset();
		};
	}

	async function confirmLinkJoin() {
		const code = linkJoinCode;
		if (!code) return;
		const trimmed = linkJoinDisplayName.trim();
		if (!trimmed) {
			toast.error('Please enter your display name.');
			return;
		}
		linkJoinBusy = true;
		linkJoinError = null;
		try {
			saveSessionDisplayName(trimmed);
			const { userId } = getOrCreateSessionUser();
			const res = await apiClient.joinRoom({
				join_code: code,
				user_id: userId,
				display_name: trimmed
			});
			if (!res.success || !res.room_id) {
				const msg = res.message || 'Could not join this room.';
				if (isJoinFailureForRemovedRoom(msg)) {
					removeRecentRoom(code);
				}
				throw new Error(msg);
			}
			if (linkJoinLifecycle.cancelled) return;
			linkJoinLifecycle.endSession = beginRoomSession(res.room_id);
			linkJoinCode = null;
			sessionUser = getOrCreateSessionUser();
		} catch (err: unknown) {
			if (linkJoinLifecycle.cancelled) return;
			const msg = err instanceof Error ? err.message : '';
			if (isJoinFailureForRemovedRoom(msg)) {
				removeRecentRoom(code);
			}
			linkJoinError = msg || 'Could not join this room.';
		} finally {
			linkJoinBusy = false;
		}
	}

	function showPendingSpotifyLinkToast() {
		const payload = readAndClearSpotifyLinkToast();
		if (!payload) return;
		if (payload.type === 'success') toast.success(payload.message);
		else if (payload.type === 'message') toast.message(payload.message);
		else toast.error(payload.message);
	}

	onMount(() => {
		linkJoinLifecycle.cancelled = false;
		linkJoinLifecycle.endSession = undefined;
		const segment = page.params.roomId ?? '';
		const parsed = parseRoomSlug(segment);

		sessionUser = getOrCreateSessionUser();
		renameDisplayName = sessionUser.displayName;
		showPendingSpotifyLinkToast();

		if (parsed.kind === 'invalid') {
			roomStore.reset();
			roomStore.setLoading(false);
			roomStore.setError('This link is not a valid room or join code.');
			return undefined;
		}

		if (parsed.kind === 'joinCode') {
			roomStore.reset();
			const storedDisplayName = getOrCreateSessionUser().displayName.trim();
			if (storedDisplayName) {
				roomStore.setLoading(true);
				linkJoinCode = null;
				void (async () => {
					try {
						const { userId } = getOrCreateSessionUser();
						const res = await apiClient.joinRoom({
							join_code: parsed.joinCode,
							user_id: userId,
							display_name: storedDisplayName
						});
						if (!res.success || !res.room_id) {
							const msg = res.message || 'Could not join this room.';
							if (isJoinFailureForRemovedRoom(msg)) {
								removeRecentRoom(parsed.joinCode);
							}
							throw new Error(msg);
						}
						if (linkJoinLifecycle.cancelled) return;
						linkJoinLifecycle.endSession = beginRoomSession(res.room_id);
						sessionUser = getOrCreateSessionUser();
					} catch (err: unknown) {
						if (linkJoinLifecycle.cancelled) return;
						const msg = err instanceof Error ? err.message : '';
						if (isJoinFailureForRemovedRoom(msg)) {
							removeRecentRoom(parsed.joinCode);
						}
						roomStore.setLoading(false);
						roomStore.setError(msg || 'Could not join this room.');
					}
				})();
				return () => {
					linkJoinLifecycle.cancelled = true;
					linkJoinLifecycle.endSession?.();
					linkJoinLifecycle.endSession = undefined;
				};
			}

			roomStore.setLoading(false);
			linkJoinCode = parsed.joinCode;
			const generatedDisplayName = generateRandomDisplayName();
			linkJoinDisplayName = generatedDisplayName;
			saveSessionDisplayName(generatedDisplayName);
			linkJoinError = null;
			return () => {
				linkJoinLifecycle.cancelled = true;
				linkJoinLifecycle.endSession?.();
				linkJoinLifecycle.endSession = undefined;
			};
		}

		return beginRoomSession(parsed.roomId);
	});
</script>

<svelte:head>
	<title>WunschKonzert room</title>
</svelte:head>

<div class="bg-background min-h-[100dvh] pb-10">
	<div class="mx-auto flex w-full max-w-7xl min-w-0 flex-col gap-6 px-6 py-6 sm:gap-8 sm:py-10">
		{#if linkJoinCode && !$roomStore.roomState}
			<Card class="mx-auto w-full max-w-md">
				<CardHeader>
					<CardTitle>Join room</CardTitle>
					<CardDescription>
						You opened a room link. Choose how your name appears to others.
					</CardDescription>
					<p class="text-muted-foreground font-mono text-sm tracking-wide">
						Code {linkJoinCode}
					</p>
				</CardHeader>
				<CardContent class="flex flex-col gap-4">
					<DisplayNameInput
						id="wk-link-join-display"
						bind:value={linkJoinDisplayName}
						disabled={linkJoinBusy}
						maxlength={60}
					/>
					{#if linkJoinError}
						<p class="text-destructive text-sm">{linkJoinError}</p>
					{/if}
					<div class="flex flex-col gap-2 min-[400px]:flex-row min-[400px]:flex-wrap">
						<Button
							type="button"
							class="w-full min-[400px]:w-auto"
							disabled={linkJoinBusy}
							onclick={() => void confirmLinkJoin()}
						>
							{linkJoinBusy ? 'Joining…' : 'Join room'}
						</Button>
						<Button variant="outline" href="/" class="w-full min-[400px]:w-auto">Back home</Button>
					</div>
				</CardContent>
			</Card>
		{:else if $roomStore.loading && !$roomStore.roomState}
			<LoadingState message="Loading room…" />
		{:else if $roomStore.error && !$roomStore.roomState}
			<EmptyState title="Room unavailable" description={$roomStore.error}>
				<Button href="/">Back home</Button>
			</EmptyState>
		{:else if $roomStore.roomState && sessionUser}
			{@const rs = $roomStore.roomState}
			{@const isHost = rs.host?.userId === sessionUser.userId}
			{@const current = getCurrentSong(rs)}
			{@const currentUserId = sessionUser.userId}
			{@const currentSkipVotes = current
				? current.feedback.filter((feedback) => feedback.type === 'skip')
				: []}
			{@const currentSkipCount = currentSkipVotes.length}
			{@const currentRequiredVotes = Math.floor(rs.users.length / 2) + 1}
			{@const currentUserSkipped = current
				? currentSkipVotes.some((feedback) => feedback.userId === currentUserId)
				: false}
			{@const isLocalTrackMatch =
				current &&
				sdkPlayerState?.trackId &&
				current.track.providerTrackId.includes(sdkPlayerState.trackId) &&
				current.queueEntryId === lastPlayedQueueEntryId}
			{@const isTransitioning = isLocalTrackMatch && playInitiatedEntryId === current.queueEntryId}
			{@const durationMs =
				isHost && sdkPlayerState && isLocalTrackMatch && sdkPlayerState.durationMs > 0
					? sdkPlayerState.durationMs
					: current
						? Math.max(0, current.track.duration) * 1000
						: 0}
			{@const positionMs =
				isHost && sdkPlayerState && isLocalTrackMatch && !isTransitioning
					? sdkPlayerState.positionMs
					: (rs.playback?.positionMs ?? 0)}
			{@const inviteUrl = rs.room ? `${page.url.origin}/room/${rs.room.joinCode}` : ''}
			{@const queuedTrackIds = activeQueuedTrackIds(rs)}
			{@const replayPanelVote =
				rs.replayVote ??
				(current ? clientReplayVoteFromPlayingEntry(current, rs, positionMs, durationMs) : null)}
			{@const replayMajorityVotes = replayPanelVote
				? replayMajorityThreshold(replayPanelVote.activeUserCount)
				: 0}

			<header
				class="flex flex-row flex-wrap gap-3 sm:items-center sm:justify-between w-[calc(100%-40px)]"
			>
				<div class="flex min-w-0 items-center gap-3">
					<img src="/logo.svg" alt="WunschKonzert logo" class="h-8 w-8 shrink-0 sm:h-10 sm:w-10" />
					<div class="min-w-0">
						<h1 class="truncate text-2xl font-semibold tracking-tight">
							{rs.room?.name || 'Room'}
						</h1>
						<p class="text-muted-foreground font-mono text-sm tracking-wide">
							Code {rs.room?.joinCode || 'N/A'}
						</p>
					</div>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<InvitePanelDialog joinCode={rs.room?.joinCode || ''} {inviteUrl} class="shrink-0" />
					{#if $roomStore.connected}
						<Badge variant="success">Live</Badge>
					{:else}
						<Badge variant="outline">Reconnecting…</Badge>
					{/if}
					{#if $roomStore.error}
						<Badge variant="destructive" class="max-w-[12rem] truncate">{$roomStore.error}</Badge>
					{/if}
				</div>
			</header>

			<main class="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-8">
				<section class="flex min-w-0 flex-col gap-3 lg:col-span-4" aria-labelledby="wk-now-playing">
					<h2 id="wk-now-playing" class="text-sm font-medium">Now playing</h2>
					<CurrentSongCard
						entry={current}
						skipCount={currentSkipCount}
						requiredVotes={currentRequiredVotes}
						hasSkipVoted={currentUserSkipped}
						busy={voteBusyId === current?.queueEntryId}
						replay={replayPanelVote
							? {
									voteCount: replayPanelVote.voteCount,
									neededVotes: replayMajorityVotes,
									hasVoted: replayPanelVote.voterUserIds.includes(sessionUser.userId),
									status: replayPanelVote.status,
									closesAt: replayPanelVote.closesAt,
									onToggle: () => void handleVote(replayPanelVote.targetQueueEntryId, 'replay')
								}
							: undefined}
						onToggleSkip={() => {
							if (!current) return;
							void handleVote(current.queueEntryId, 'skip');
						}}
					/>
					{#if current && durationMs > 0}
						<PlaybackProgress {positionMs} {durationMs} playbackState={rs.playback?.state} />
					{/if}
					{#if isHost && playbackNeedsGesture}
						<div
							role="status"
							class="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm"
						>
							<p class="mb-2">
								{#if appleMusicDeferInitialPlay}
									Tap to load the current song, then press Resume to play.
								{:else}
									Your browser blocked autoplay. Tap below or anywhere on the page to continue.
								{/if}
							</p>
							<Button type="button" size="sm" onclick={() => unlockHostPlayback()}>
								{appleMusicDeferInitialPlay ? 'Load track' : 'Continue'}
							</Button>
						</div>
					{/if}
					{#if isHost}
						<PlaybackControls
							playbackState={rs.playback?.state}
							busy={playbackBusy}
							onPlaybackAction={handlePlayback}
						/>
					{/if}
				</section>

				<section class="flex min-w-0 flex-col gap-3 lg:col-span-8" aria-labelledby="wk-queue">
					<div class="flex items-center justify-between">
						<h2 id="wk-queue" class="text-sm font-medium">Queue</h2>
						<SongHistoryModal roomState={rs} onAddTrack={handleAddTrack} />
					</div>
					<QueueList
						entries={queueWithoutCurrent(rs)}
						userId={sessionUser.userId}
						hostId={rs.host.userId}
						totalMembers={countActiveRoomMembers($roomStore.roomState)}
						{voteBusyId}
						onVote={handleVote}
						onRemove={handleRemove}
					/>
				</section>

				<section
					class="flex min-w-0 flex-col gap-3 lg:col-span-8"
					aria-labelledby="wk-search-heading"
				>
					<h2 id="wk-search-heading" class="text-sm font-medium">Add a song</h2>
					<Card>
						<CardHeader class="pb-2">
							<CardTitle class="text-base">Search</CardTitle>
							<CardDescription>
								Results come from the room provider ({providerLabel(rs.room.supportedProviderId)}).
							</CardDescription>
						</CardHeader>
						<CardContent>
							<SongSearchPanel
								roomId={rs.room?.roomId || ''}
								{queuedTrackIds}
								onAddTrack={handleAddTrack}
							/>
						</CardContent>
					</Card>
				</section>

				<section class="min-w-0 lg:col-span-4" aria-labelledby="wk-people">
					<h2 id="wk-people" class="mb-3 text-sm font-medium">Who is here</h2>
					<div class="flex flex-col gap-3">
						{#if rs.transfer}
							<HostTransferPanel
								transfer={rs.transfer}
								roomState={rs}
								currentUserId={sessionUser.userId}
								providerLinked={providerLinkedForTransfer}
								busy={hostTransferActionBusy}
								linkBusy={hostTransferLinkBusy}
								onAccept={() => void handleAcceptHostTransfer()}
								onReject={() => void handleRejectHostTransfer()}
								onLinkProvider={() => void linkProviderForHostTransfer()}
							/>
						{/if}
						{#if rs.systemMessages?.length}
							<SystemMessagesList messages={rs.systemMessages} />
						{/if}
						<UserList
							users={rs.users}
							hostUserId={rs.host.userId}
							currentUserId={sessionUser.userId}
							canOfferHostTransfer={isHost && !rs.transfer}
							{hostTransferBusyUserId}
							onEditSelf={openRenameDialog}
							onOfferHostTransfer={(userId) => void handleOfferHostTransfer(userId)}
						/>
					</div>
				</section>
			</main>

			<footer
				class="border-border flex flex-col gap-2 border-t pt-6 min-[400px]:flex-row min-[400px]:flex-wrap"
			>
				{#if isHost}
					<DeleteRoomButton roomId={rs.room?.roomId || ''} userId={sessionUser.userId} />
				{:else}
					<LeaveRoomButton roomId={rs.room?.roomId || ''} userId={sessionUser.userId} />
					<Button variant="ghost" href="/" class="w-full min-[400px]:w-auto">Home</Button>
				{/if}
			</footer>

			<Dialog.Root bind:open={renameDialogOpen}>
				<Dialog.Content class="max-w-md">
					<Dialog.Header>
						<Dialog.Title>Edit display name</Dialog.Title>
						<Dialog.Description>
							Choose how your name appears to everyone in this room.
						</Dialog.Description>
					</Dialog.Header>
					<form class="flex flex-col gap-4" onsubmit={handleRenameSubmit}>
						<Input
							type="text"
							maxlength={60}
							placeholder="How others see you"
							bind:value={renameDisplayName}
							disabled={renameBusy}
							autocomplete="nickname"
						/>
						<div class="flex justify-end gap-2">
							<Button
								type="button"
								variant="outline"
								disabled={renameBusy}
								onclick={() => (renameDialogOpen = false)}
							>
								Cancel
							</Button>
							<Button type="submit" disabled={renameBusy}>
								{renameBusy ? 'Saving…' : 'Save'}
							</Button>
						</div>
					</form>
				</Dialog.Content>
			</Dialog.Root>
		{:else}
			<LoadingState message="Preparing room…" />
		{/if}
	</div>
</div>
