<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { apiClient } from '$lib/api/client';
	import { roomStore, getCurrentSong } from '$lib/stores/room';
	import { RoomSocketClient } from '$lib/realtime/roomSocket';
	import { browser } from '$app/environment';
	import { getOrCreateSessionUser } from '$lib/session/userSession';
	import {
		isJoinFailureForRemovedRoom,
		recordRecentRoom,
		removeRecentRoom
	} from '$lib/session/recentRooms';
	import type { QueueEntryDto, RoomStateDto, TrackDto, VoteRequest } from '$lib/types/api';
	import { Badge } from '$lib/components/ui/badge';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import CurrentSongCard from '$lib/components/mvp/CurrentSongCard.svelte';
	import PlaybackProgress from '$lib/components/mvp/PlaybackProgress.svelte';
	import PlaybackControls from '$lib/components/mvp/PlaybackControls.svelte';
	import QueueList from '$lib/components/mvp/QueueList.svelte';
	import SongSearchPanel from '$lib/components/mvp/SongSearchPanel.svelte';
	import UserList from '$lib/components/mvp/UserList.svelte';
	import LeaveRoomButton from '$lib/components/mvp/LeaveRoomButton.svelte';
	import DeleteRoomButton from '$lib/components/mvp/DeleteRoomButton.svelte';
	import InvitePanelDialog from '$lib/components/mvp/InvitePanelDialog.svelte';
	import LoadingState from '$lib/components/mvp/LoadingState.svelte';
	import EmptyState from '$lib/components/mvp/EmptyState.svelte';
	import { Button } from '$lib/components/ui/button';
	import { toast } from 'svelte-sonner';
	import { parseRoomSlug } from '$lib/room/slug';

	let sessionUser = $state<{ userId: string; displayName: string } | null>(null);
	let recordedRecentThisMount = $state(false);
	let socketClient = $state<RoomSocketClient | null>(null);
	let voteBusyId = $state<string | null>(null);
	let playbackBusy = $state(false);

	function queueWithoutCurrent(state: RoomStateDto | null): QueueEntryDto[] {
		if (!state) return [];
		const currentId = state.playback?.currentQueueEntryId;
		return currentId
			? state.queue.filter((e) => e.queueEntryId !== currentId)
			: state.queue.filter((e) => e.status !== 'playing');
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

	async function handlePlayback(action: 'pause' | 'resume') {
		const uid = sessionUser?.userId;
		if (!uid || !socketClient || !socketClient.isConnected()) {
			toast.error('Not connected to room');
			return;
		}
		playbackBusy = true;
		try {
			const sent = await socketClient.setPlayback(uid, action);
			if (!sent) {
				throw new Error('Playback command failed');
			}
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Playback command failed');
		} finally {
			playbackBusy = false;
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

	async function handleAddTrack(track: TrackDto) {
		const uid = sessionUser?.userId;
		if (!uid || !socketClient || !socketClient.isConnected()) {
			throw new Error('Not connected to room');
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

	onMount(() => {
		const segment = page.params.roomId ?? '';
		const parsed = parseRoomSlug(segment);

		sessionUser = getOrCreateSessionUser();

		if (parsed.kind === 'invalid') {
			roomStore.reset();
			roomStore.setLoading(false);
			roomStore.setError('This link is not a valid room or join code.');
			return undefined;
		}

		function beginRoomSession(roomId: string, opts?: { joinCodeForRecents?: string }): () => void {
			roomStore.reset();
			roomStore.setLoading(true);

			let roomDeletedRedirectDone = false;
			const unsubDeleted = roomStore.subscribe((ui) => {
				if (roomDeletedRedirectDone) return;
				if (ui.roomState?.room.status === 'deleted') {
					roomDeletedRedirectDone = true;
					removeRecentRoom(ui.roomState.room.joinCode);
					toast.message('Room ended by host');
					void goto(resolve('/'));
				}
			});

			void apiClient
				.getRoomState(roomId)
				.then((state) => roomStore.setRoomState(state))
				.catch((err: unknown) => {
					roomStore.setLoading(false);
					const msg = err instanceof Error ? err.message : '';
					const code = opts?.joinCodeForRecents;
					if (code && isJoinFailureForRemovedRoom(msg)) {
						removeRecentRoom(code);
					}
					roomStore.setError(msg || 'Could not load room');
				});

			const socket = new RoomSocketClient(roomId, {
				onState: (s) => roomStore.setRoomState(s),
				onError: (m) => {
					toast.error(m);
					roomStore.setError(m);
				},
				onConnectionChange: (c) => roomStore.setConnected(c)
			});
			socketClient = socket;
			socket.connect();

			return () => {
				unsubDeleted();
				socket.disconnect();
				socketClient = null;
				roomStore.reset();
			};
		}

		if (parsed.kind === 'joinCode') {
			roomStore.reset();
			roomStore.setLoading(true);
			let cancelled = false;
			let endSession: (() => void) | undefined;
			void (async () => {
				try {
					const { userId } = getOrCreateSessionUser();
					const res = await apiClient.joinRoom({
						room_id: parsed.joinCode,
						user_id: userId
					});
					if (!res.success || !res.room_id) {
						const msg = res.message || 'Could not join this room.';
						if (isJoinFailureForRemovedRoom(msg)) {
							removeRecentRoom(parsed.joinCode);
						}
						throw new Error(msg);
					}
					if (cancelled) return;
					endSession = beginRoomSession(res.room_id, {
						joinCodeForRecents: parsed.joinCode
					});
				} catch (err: unknown) {
					if (cancelled) return;
					const msg = err instanceof Error ? err.message : '';
					if (isJoinFailureForRemovedRoom(msg)) {
						removeRecentRoom(parsed.joinCode);
					}
					roomStore.setLoading(false);
					roomStore.setError(msg || 'Could not join this room.');
				}
			})();
			return () => {
				cancelled = true;
				endSession?.();
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
		{#if $roomStore.loading && !$roomStore.roomState}
			<LoadingState message="Loading room…" />
		{:else if $roomStore.error && !$roomStore.roomState}
			<EmptyState title="Room unavailable" description={$roomStore.error}>
				<Button href="/">Back home</Button>
			</EmptyState>
		{:else if $roomStore.roomState && sessionUser}
			{@const rs = $roomStore.roomState}
			{@const isHost = rs.host.userId === sessionUser.userId}
			{@const current = getCurrentSong(rs)}
			{@const durationMs = current ? Math.max(0, current.track.duration) * 1000 : 0}
			{@const positionMs = rs.playback?.positionMs ?? 0}
			{@const inviteUrl = `${page.url.origin}/room/${rs.room.joinCode}`}

			<header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
				<div class="min-w-0">
					<h1 class="truncate text-2xl font-semibold tracking-tight">{rs.room.name}</h1>
					<p class="text-muted-foreground font-mono text-sm tracking-wide">
						Code {rs.room.joinCode}
					</p>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<InvitePanelDialog joinCode={rs.room.joinCode} {inviteUrl} class="shrink-0" />
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
					<CurrentSongCard entry={current} />
					{#if current && durationMs > 0}
						<PlaybackProgress {positionMs} {durationMs} state={rs.playback?.state} />
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
					<h2 id="wk-queue" class="text-sm font-medium">Queue</h2>
					<QueueList
						entries={queueWithoutCurrent(rs)}
						userId={sessionUser.userId}
						{voteBusyId}
						onVote={handleVote}
					/>
				</section>

				<section class="flex min-w-0 flex-col gap-3 lg:col-span-8" aria-labelledby="wk-search">
					<h2 id="wk-search" class="text-sm font-medium">Add a song</h2>
					<Card>
						<CardHeader class="pb-2">
							<CardTitle class="text-base">Search</CardTitle>
							<CardDescription>Results come from the room provider (Spotify).</CardDescription>
						</CardHeader>
						<CardContent>
							<SongSearchPanel roomId={rs.room.roomId} onAddTrack={handleAddTrack} />
						</CardContent>
					</Card>
				</section>

				<section class="min-w-0 lg:col-span-4" aria-labelledby="wk-people">
					<h2 id="wk-people" class="mb-3 text-sm font-medium">Who is here</h2>
					<UserList
						users={rs.users}
						hostUserId={rs.host.userId}
						currentUserId={sessionUser.userId}
					/>
				</section>
			</main>

			<footer
				class="border-border flex flex-col gap-2 border-t pt-6 min-[400px]:flex-row min-[400px]:flex-wrap"
			>
				{#if isHost}
					<DeleteRoomButton
						roomId={rs.room.roomId}
						joinCode={rs.room.joinCode}
						userId={sessionUser.userId}
					/>
				{:else}
					<LeaveRoomButton roomId={rs.room.roomId} userId={sessionUser.userId} />
					<Button variant="ghost" href="/" class="w-full min-[400px]:w-auto">Home</Button>
				{/if}
			</footer>
		{:else}
			<LoadingState message="Preparing room…" />
		{/if}
	</div>
</div>
