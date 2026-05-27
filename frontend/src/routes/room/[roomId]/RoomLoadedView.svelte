<script lang="ts">
	import { page } from '$app/state';
	import {
		roomStore,
		getCurrentSong,
		queueWithoutCurrent,
		activeQueuedTrackIds,
		countActiveRoomMembers,
		clientReplayVoteFromPlayingEntry,
		replayMajorityThreshold
	} from '$lib/stores/room';
	import type { LastActivityDto, RoomStateDto } from '$lib/types/api';
	import type { TrackDto, VoteRequest } from '$lib/types/api';
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
	import LastActivityLog from '$lib/components/room/activity/LastActivityLog.svelte';
	import LeaveRoomButton from '$lib/components/room/actions/LeaveRoomButton.svelte';
	import DeleteRoomButton from '$lib/components/room/actions/DeleteRoomButton.svelte';
	import InvitePanelDialog from '$lib/components/room/invite/InvitePanelDialog.svelte';
	import SongHistoryModal from '$lib/components/room/history/SongHistoryModal.svelte';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { providerLabel } from '$lib/providers/constants';
	import type { useHostPlayback } from './useHostPlayback.svelte';

	type HostPlayback = ReturnType<typeof useHostPlayback>;

	type Props = {
		sessionUser: { userId: string; displayName: string };
		roomState: RoomStateDto;
		activityLog: LastActivityDto[];
		hostPlayback: HostPlayback;
		voteBusyId: string | null;
		renameDisplayName: string;
		renameBusy: boolean;
		renameDialogOpen: boolean;
		hostTransferBusyUserId: string | null;
		hostTransferActionBusy: boolean;
		hostTransferLinkBusy: boolean;
		providerLinkedForTransfer: boolean;
		onVote: (queueEntryId: string, vote: VoteRequest['vote_type']) => void;
		onRemove: (queueEntryId: string) => void;
		onPlayback: (action: 'pause' | 'resume') => void;
		onAddTrack: (track: TrackDto) => Promise<void>;
		onMarkActivityRead: () => void;
		onOpenRename: () => void;
		onRenameSubmit: (event: Event) => void;
		onOfferHostTransfer: (userId: string) => void;
		onAcceptHostTransfer: () => void;
		onRejectHostTransfer: () => void;
		onLinkProvider: () => void;
	};

	let {
		sessionUser,
		roomState: rs,
		activityLog,
		hostPlayback,
		voteBusyId,
		renameDisplayName = $bindable(),
		renameBusy,
		renameDialogOpen = $bindable(),
		hostTransferBusyUserId,
		hostTransferActionBusy,
		hostTransferLinkBusy,
		providerLinkedForTransfer,
		onVote,
		onRemove,
		onPlayback,
		onAddTrack,
		onMarkActivityRead,
		onOpenRename,
		onRenameSubmit,
		onOfferHostTransfer,
		onAcceptHostTransfer,
		onRejectHostTransfer,
		onLinkProvider
	}: Props = $props();

	const isHost = $derived(rs.host?.userId === sessionUser.userId);
	const current = $derived(getCurrentSong(rs));
	const currentUserId = $derived(sessionUser.userId);
	const currentSkipVotes = $derived(
		current ? current.feedback.filter((feedback) => feedback.type === 'skip') : []
	);
	const currentSkipCount = $derived(currentSkipVotes.length);
	const currentRequiredVotes = $derived(Math.floor(rs.users.length / 2) + 1);
	const currentUserSkipped = $derived(
		current ? currentSkipVotes.some((feedback) => feedback.userId === currentUserId) : false
	);
	const sdkPlayerState = $derived(hostPlayback.sdkPlayerState);
	const lastPlayedQueueEntryId = $derived(hostPlayback.lastPlayedQueueEntryId);
	const playInitiatedEntryId = $derived(hostPlayback.playInitiatedEntryId);
	const isLocalTrackMatch = $derived(
		current &&
			sdkPlayerState?.trackId &&
			current.track.providerTrackId.includes(sdkPlayerState.trackId) &&
			current.queueEntryId === lastPlayedQueueEntryId
	);
	const isTransitioning = $derived(
		isLocalTrackMatch && playInitiatedEntryId === current?.queueEntryId
	);
	const durationMs = $derived(
		isHost && sdkPlayerState && isLocalTrackMatch && sdkPlayerState.durationMs > 0
			? sdkPlayerState.durationMs
			: current
				? Math.max(0, current.track.duration) * 1000
				: 0
	);
	const positionMs = $derived(
		isHost && sdkPlayerState && isLocalTrackMatch && !isTransitioning
			? sdkPlayerState.positionMs
			: (rs.playback?.positionMs ?? 0)
	);
	const inviteUrl = $derived(rs.room ? `${page.url.origin}/room/${rs.room.joinCode}` : '');
	const queuedTrackIds = $derived(activeQueuedTrackIds(rs));
	const replayPanelVote = $derived(
		rs.replayVote ??
			(current ? clientReplayVoteFromPlayingEntry(current, rs, positionMs, durationMs) : null)
	);
	const replayMajorityVotes = $derived(
		replayPanelVote ? replayMajorityThreshold(replayPanelVote.activeUserCount) : 0
	);
</script>

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
		<LastActivityLog activities={activityLog} roomState={rs} onMarkRead={onMarkActivityRead} />
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
						onToggle: () => void onVote(replayPanelVote.targetQueueEntryId, 'replay')
					}
				: undefined}
			onToggleSkip={() => {
				if (!current) return;
				void onVote(current.queueEntryId, 'skip');
			}}
		/>
		{#if current && durationMs > 0}
			<PlaybackProgress {positionMs} {durationMs} playbackState={rs.playback?.state} />
		{/if}
		{#if isHost && hostPlayback.playbackNeedsGesture}
			<div
				role="status"
				class="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm"
			>
				<p class="mb-2">
					{#if hostPlayback.appleMusicDeferInitialPlay}
						Tap to load the current song, then press Resume to play.
					{:else}
						Your browser blocked autoplay. Tap below or anywhere on the page to continue.
					{/if}
				</p>
				<Button type="button" size="sm" onclick={() => hostPlayback.unlockHostPlayback()}>
					{hostPlayback.appleMusicDeferInitialPlay ? 'Load track' : 'Continue'}
				</Button>
			</div>
		{/if}
		{#if isHost}
			<PlaybackControls
				playbackState={rs.playback?.state}
				busy={hostPlayback.playbackBusy}
				onPlaybackAction={onPlayback}
			/>
		{/if}
	</section>

	<section class="flex min-w-0 flex-col gap-3 lg:col-span-8" aria-labelledby="wk-queue">
		<div class="flex items-center justify-between">
			<h2 id="wk-queue" class="text-sm font-medium">Queue</h2>
			<SongHistoryModal roomState={rs} onAddTrack={onAddTrack} />
		</div>
		<QueueList
			entries={queueWithoutCurrent(rs)}
			userId={sessionUser.userId}
			hostId={rs.host.userId}
			totalMembers={countActiveRoomMembers($roomStore.roomState)}
			{voteBusyId}
			onVote={onVote}
			onRemove={onRemove}
		/>
	</section>

	<section class="flex min-w-0 flex-col gap-3 lg:col-span-8" aria-labelledby="wk-search-heading">
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
					onAddTrack={onAddTrack}
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
					onAccept={() => void onAcceptHostTransfer()}
					onReject={() => void onRejectHostTransfer()}
					onLinkProvider={() => void onLinkProvider()}
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
				onEditSelf={onOpenRename}
				onOfferHostTransfer={(userId) => void onOfferHostTransfer(userId)}
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
		<form class="flex flex-col gap-4" onsubmit={onRenameSubmit}>
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
