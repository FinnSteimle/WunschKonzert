import { onMount } from 'svelte';
import { browser } from '$app/environment';
import { page } from '$app/state';
import { apiClient } from '$lib/api/client';
import { joinRoomByCode } from '$lib/room/joinRoomByCode';
import { parseRoomSlug } from '$lib/room/slug';
import type { RoomSocketClient } from '$lib/realtime/roomSocket';
import { roomStore, displayNameForUser } from '$lib/stores/room';
import {
	generateRandomDisplayName,
	getOrCreateSessionUser,
	saveSessionDisplayName
} from '$lib/session/userSession';
import type { LastActivityDto, TrackDto, VoteRequest } from '$lib/types/api';
import type { ProviderId } from '$lib/types/api';
import { linkAppleMusicAccount } from '$lib/providers/appleMusicAuth';
import { providerLabel } from '$lib/providers/constants';
import { isProviderLinkedForUser } from '$lib/providers/linkStatus';
import { toast } from 'svelte-sonner';
import { get } from 'svelte/store';
import { useHostPlayback } from './useHostPlayback.svelte';
import { createBeginRoomSession } from './useRoomSession.svelte';
import { useRoomSpotifyOAuth } from './useRoomSpotifyOAuth.svelte';
import { useRoomEffects } from './useRoomEffects.svelte';

export function useRoomPage() {
	let roomUi = $state(get(roomStore));

	$effect(() => {
		return roomStore.subscribe((value) => {
			roomUi = value;
		});
	});

	let sessionUser = $state<{ userId: string; displayName: string } | null>(
		browser ? getOrCreateSessionUser() : null
	);
	let socketClient = $state<RoomSocketClient | null>(null);
	let voteBusyId = $state<string | null>(null);
	let renameDisplayName = $state('');
	let renameBusy = $state(false);
	let renameDialogOpen = $state(false);
	let hostTransferBusyUserId = $state<string | null>(null);
	let hostTransferActionBusy = $state(false);
	let hostTransferLinkBusy = $state(false);
	let providerLinkedForTransfer = $state(false);
	let activityLog = $state<LastActivityDto[]>([]);
	let activityLogRoomId = $state<string | null>(null);
	let lastActivitySignature = $state<string | undefined>(undefined);

	let linkJoinCode = $state<string | null>(null);
	let linkJoinDisplayName = $state('');
	let linkJoinBusy = $state(false);
	let linkJoinError = $state<string | null>(null);
	const linkJoinLifecycle = {
		cancelled: false,
		endSession: undefined as (() => void) | undefined
	};

	const hostPlayback = useHostPlayback({
		getSocketClient: () => socketClient
	});

	const { syncActivityFromRoomState } = useRoomEffects({
		getSessionUser: () => sessionUser,
		getRoomUi: () => roomUi,
		hostPlayback,
		getActivityState: () => ({
			activityLog,
			activityLogRoomId,
			lastActivitySignature
		}),
		setActivityState: (next) => {
			activityLog = next.activityLog;
			activityLogRoomId = next.activityLogRoomId;
			lastActivitySignature = next.lastActivitySignature;
		},
		clearHostTransferBusy: () => {
			hostTransferBusyUserId = null;
		}
	});

	const beginRoomSession = createBeginRoomSession({
		getSessionUser: () => sessionUser,
		setSocketClient: (client) => {
			socketClient = client;
		},
		hostPlayback,
		syncActivityFromRoomState
	});

	async function refreshProviderLinkStatus(forProvider?: ProviderId): Promise<boolean> {
		const uid = sessionUser?.userId;
		const providerId =
			forProvider ??
			(() => {
				const id = get(roomStore).roomState?.room.supportedProviderId;
				return id === 'spotify' || id === 'apple-music' ? id : undefined;
			})();
		if (!uid || !providerId) {
			providerLinkedForTransfer = false;
			return false;
		}
		const linked = await isProviderLinkedForUser(providerId, uid);
		providerLinkedForTransfer = linked;
		return linked;
	}

	const { showPendingSpotifyLinkToast } = useRoomSpotifyOAuth({
		setProviderLinkedForTransfer: (linked) => {
			providerLinkedForTransfer = linked;
		},
		refreshProviderLinkStatus,
		getTransferTargetUserId: () => {
			const transfer = roomUi.roomState?.transfer;
			const uid = sessionUser?.userId;
			return transfer?.toUserId === uid ? uid : undefined;
		}
	});

	function markActivityRead(): void {
		activityLog = [];
	}

	function requireConnectedSocket(): RoomSocketClient | null {
		const uid = sessionUser?.userId;
		if (!uid || !socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return null;
		}
		return socketClient;
	}

	async function handleVote(queueEntryId: string, vote: VoteRequest['vote_type']) {
		const socket = requireConnectedSocket();
		if (!socket || !sessionUser) return;
		voteBusyId = queueEntryId;
		try {
			const sent = await socket.sendVote(queueEntryId, sessionUser.userId, vote);
			if (!sent) throw new Error('Vote failed');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Vote failed');
		} finally {
			voteBusyId = null;
		}
	}

	async function handleRemove(queueEntryId: string) {
		const socket = requireConnectedSocket();
		if (!socket || !sessionUser) return;
		voteBusyId = queueEntryId;
		try {
			const sent = socket.removeQueueEntry(queueEntryId, sessionUser.userId);
			if (!sent) throw new Error('Remove failed');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Remove failed');
		} finally {
			voteBusyId = null;
		}
	}

	function saveDisplayNameChange(): boolean {
		const socket = requireConnectedSocket();
		const uid = sessionUser?.userId;
		const trimmed = renameDisplayName.trim();
		if (!socket || !uid) return false;
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
			const sent = socket.renameDisplayName(uid, trimmed);
			if (!sent) throw new Error('Rename failed');
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
		if (saveDisplayNameChange()) {
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
		const socket = requireConnectedSocket();
		if (!socket) return;
		hostTransferBusyUserId = targetUserId;
		try {
			const sent = socket.initiateHostTransfer(uid, targetUserId);
			if (!sent) throw new Error('Could not send host transfer invite');
			toast.message('Host invite sent to ' + displayNameForUser(rs, targetUserId) + '.');
		} catch (err) {
			hostTransferBusyUserId = null;
			toast.error(err instanceof Error ? err.message : 'Host transfer failed');
		}
	}

	async function handleAcceptHostTransfer() {
		const uid = sessionUser?.userId;
		const rs = get(roomStore).roomState;
		const transfer = rs?.transfer;
		if (!uid || !transfer || transfer.toUserId !== uid) return;
		const socket = requireConnectedSocket();
		if (!socket) return;
		hostTransferActionBusy = true;
		try {
			const linked = await refreshProviderLinkStatus();
			const providerId = rs.room.supportedProviderId;
			if (!linked) {
				const label = providerLabel(
					providerId === 'spotify' || providerId === 'apple-music' ? providerId : undefined
				);
				toast.error(
					`${label} is not linked for this browser session. Use “Link ${label} account” below, then accept again.`
				);
				return;
			}
			const sent = socket.acceptHostTransfer(uid, transfer.transferId);
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
		const socket = requireConnectedSocket();
		if (!socket) return;
		hostTransferActionBusy = true;
		try {
			const sent = socket.rejectHostTransfer(uid, transfer.transferId);
			if (!sent) throw new Error('Could not decline host transfer');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not decline host transfer');
		} finally {
			hostTransferActionBusy = false;
		}
	}

	async function linkProviderForHostTransfer() {
		const uid = sessionUser?.userId;
		const id = get(roomStore).roomState?.room.supportedProviderId;
		const providerId = id === 'spotify' || id === 'apple-music' ? id : undefined;
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

	async function handleAddTrack(track: TrackDto) {
		const socket = requireConnectedSocket();
		if (!socket || !sessionUser) {
			throw new Error('Not connected to room');
		}

		const currentState = get(roomStore).roomState;
		if (
			currentState?.queue.some(
				(entry) => entry.track.trackId === track.trackId && entry.status !== 'played'
			)
		) {
			throw new Error('Song is already in the queue');
		}

		const sent = await socket.addToQueue(track, sessionUser.userId);
		if (!sent) {
			throw new Error('Could not add song');
		}
	}

	async function startSessionAfterJoin(
		joinCode: string,
		displayName: string
	): Promise<Awaited<ReturnType<typeof joinRoomByCode>>> {
		const result = await joinRoomByCode(joinCode, displayName);
		if (!result.ok || linkJoinLifecycle.cancelled) {
			return result;
		}
		linkJoinLifecycle.endSession = beginRoomSession(result.roomId);
		linkJoinCode = null;
		sessionUser = getOrCreateSessionUser();
		return result;
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
			const result = await startSessionAfterJoin(code, trimmed);
			if (!linkJoinLifecycle.cancelled && !result.ok) {
				linkJoinError = result.message;
			}
		} finally {
			linkJoinBusy = false;
		}
	}

	function linkJoinTeardown() {
		return () => {
			linkJoinLifecycle.cancelled = true;
			linkJoinLifecycle.endSession?.();
			linkJoinLifecycle.endSession = undefined;
		};
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

		roomStore.reset();
		const storedDisplayName = getOrCreateSessionUser().displayName.trim();
		if (storedDisplayName) {
			roomStore.setLoading(true);
			linkJoinCode = null;
			void (async () => {
				const result = await startSessionAfterJoin(parsed.joinCode, storedDisplayName);
				if (!result.ok && !linkJoinLifecycle.cancelled) {
					roomStore.setLoading(false);
					roomStore.setError(result.message || 'Could not join this room.');
				}
			})();
			return linkJoinTeardown();
		}

		roomStore.setLoading(false);
		linkJoinCode = parsed.joinCode;
		const generatedDisplayName = generateRandomDisplayName();
		linkJoinDisplayName = generatedDisplayName;
		saveSessionDisplayName(generatedDisplayName);
		linkJoinError = null;
		return linkJoinTeardown();
	});

	return {
		get sessionUser() {
			return sessionUser;
		},
		get voteBusyId() {
			return voteBusyId;
		},
		get renameDisplayName() {
			return renameDisplayName;
		},
		set renameDisplayName(v: string) {
			renameDisplayName = v;
		},
		get renameBusy() {
			return renameBusy;
		},
		get renameDialogOpen() {
			return renameDialogOpen;
		},
		set renameDialogOpen(v: boolean) {
			renameDialogOpen = v;
		},
		get hostTransferBusyUserId() {
			return hostTransferBusyUserId;
		},
		get hostTransferActionBusy() {
			return hostTransferActionBusy;
		},
		get hostTransferLinkBusy() {
			return hostTransferLinkBusy;
		},
		get providerLinkedForTransfer() {
			return providerLinkedForTransfer;
		},
		get activityLog() {
			return activityLog;
		},
		get linkJoinCode() {
			return linkJoinCode;
		},
		get linkJoinDisplayName() {
			return linkJoinDisplayName;
		},
		set linkJoinDisplayName(v: string) {
			linkJoinDisplayName = v;
		},
		get linkJoinBusy() {
			return linkJoinBusy;
		},
		get linkJoinError() {
			return linkJoinError;
		},
		hostPlayback,
		handleVote,
		handleRemove,
		handlePlayback: (action: 'pause' | 'resume') =>
			hostPlayback.handlePlayback(action, sessionUser?.userId),
		openRenameDialog,
		handleRenameSubmit,
		handleOfferHostTransfer,
		handleAcceptHostTransfer,
		handleRejectHostTransfer,
		linkProviderForHostTransfer,
		handleAddTrack,
		confirmLinkJoin,
		markActivityRead
	};
}
