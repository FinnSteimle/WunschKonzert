import { onMount } from 'svelte';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { resolve } from '$app/paths';
import { page } from '$app/state';
import { apiClient } from '$lib/api/client';
import { roomStore, displayNameForUser } from '$lib/stores/room';
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
import type { LastActivityDto, RoomStateDto, TrackDto, VoteRequest } from '$lib/types/api';
import type { ProviderId } from '$lib/types/api';
import { linkAppleMusicAccount } from '$lib/providers/appleMusicAuth';
import { providerLabel } from '$lib/providers/constants';
import { isProviderLinkedForUser } from '$lib/providers/linkStatus';
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
import {
	appendLastActivityFromRoomState,
	HOST_TRANSFER_EVENTS,
	REPLAY_SUCCESS_EVENTS
} from './roomPageActivity';
import { useHostPlayback } from './useHostPlayback.svelte';

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
	let recordedRecentThisMount = false;
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

	let lastReplayEventSignature = $state<string | undefined>(undefined);
	let lastHostTransferEventSignature = $state<string | undefined>(undefined);
	let spotifyOAuthQueryHandled = false;

	const hostPlayback = useHostPlayback({
		getSocketClient: () => socketClient
	});

	function reloadWithoutSpotifyQueryParams() {
		window.location.replace(buildPathWithoutSpotifyOAuthParams(window.location.href));
	}

	function markActivityRead(): void {
		activityLog = [];
	}

	function syncActivityFromRoomState(rs: RoomStateDto | null): void {
		const next = appendLastActivityFromRoomState(
			{ activityLog, activityLogRoomId, lastActivitySignature },
			rs
		);
		activityLog = next.activityLog;
		activityLogRoomId = next.activityLogRoomId;
		lastActivitySignature = next.lastActivitySignature;
	}

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

	async function handleAddTrack(track: TrackDto) {
		const uid = sessionUser?.userId;
		if (!uid || !socketClient || !socketClient.isConnected()) {
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

		try {
			const sent = await socketClient.addToQueue(track, uid);
			if (!sent) {
				throw new Error('Could not add song');
			}
		} catch (err) {
			throw new Error(err instanceof Error ? err.message : 'Could not add song');
		}
	}

	function beginRoomSession(roomId: string): () => void {
		roomStore.reset();
		roomStore.setLoading(true);

		let roomDeletedRedirectDone = false;
		const unsubDeleted = roomStore.subscribe((ui) => {
			syncActivityFromRoomState(ui.roomState);
			if (roomDeletedRedirectDone) return;
			if (ui.roomState?.room.status === 'deleted') {
				roomDeletedRedirectDone = true;
				removeRecentRoom(ui.roomState.room.joinCode);
				if (sessionUser && ui.roomState.host.userId !== sessionUser.userId) {
					toast.message('Room ended by host');
				}
				void goto(resolve('/'));
			}

			hostPlayback.maybeInitHostPlayer(
				sessionUser?.userId,
				ui.roomState?.host.userId,
				ui.roomState?.room.supportedProviderId
			);
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
			hostPlayback.teardownHostPlayback();
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

	$effect(() => {
		if (!browser) return;
		const rs = roomUi.roomState;
		const su = sessionUser;
		if (recordedRecentThisMount || !rs || !su) return;
		recordedRecentThisMount = true;
		recordRecentRoom({
			joinCode: rs.room.joinCode,
			name: rs.room.name,
			isHost: rs.host.userId === su.userId
		});
	});

	$effect(() => {
		if (!browser) return;
		const ev = roomUi.roomState?.lastEvent;
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
		const rs = roomUi.roomState;
		const su = sessionUser;
		const ev = rs?.lastEvent;
		const sig = ev ? `${ev.type}:${ev.at}` : '';
		const prev = lastHostTransferEventSignature;
		const prevHostId = hostPlayback.getLastKnownHostUserId();

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
		const rs = roomUi.roomState;
		const su = sessionUser;
		if (!rs || !su) return;
		hostPlayback.syncHostRole(su.userId);
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
			writeSpotifyLinkToast(toastPayloadAfterSpotifyLink(linked, profileWarning));
			reloadWithoutSpotifyQueryParams();
		});
	});

	$effect(() => {
		if (!browser || !sessionUser) return;
		const transfer = roomUi.roomState?.transfer;
		if (transfer?.toUserId === sessionUser.userId) {
			void refreshProviderLinkStatus();
		}
	});

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
