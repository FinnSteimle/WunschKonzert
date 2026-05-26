<script lang="ts">
	import { roomStore } from '$lib/stores/room';
	import { Button } from '$lib/components/ui/button';
	import LoadingState from '$lib/components/room/states/LoadingState.svelte';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';
	import { useRoomPage } from './useRoomPage.svelte';
	import LinkJoinCard from './LinkJoinCard.svelte';
	import RoomLoadedView from './RoomLoadedView.svelte';

	const room = useRoomPage();
</script>

<svelte:head>
	<title>WunschKonzert room</title>
</svelte:head>

<div class="bg-background min-h-[100dvh] pb-10">
	<div class="mx-auto flex w-full max-w-7xl min-w-0 flex-col gap-6 px-6 py-6 sm:gap-8 sm:py-10">
		{#if room.linkJoinCode && !$roomStore.roomState}
			<LinkJoinCard
				joinCode={room.linkJoinCode}
				bind:displayName={room.linkJoinDisplayName}
				busy={room.linkJoinBusy}
				error={room.linkJoinError}
				onConfirm={() => void room.confirmLinkJoin()}
			/>
		{:else if $roomStore.loading && !$roomStore.roomState}
			<LoadingState message="Loading room…" />
		{:else if $roomStore.error && !$roomStore.roomState}
			<EmptyState title="Room unavailable" description={$roomStore.error}>
				<Button href="/">Back home</Button>
			</EmptyState>
		{:else if $roomStore.roomState && room.sessionUser}
			<RoomLoadedView
				sessionUser={room.sessionUser}
				roomState={$roomStore.roomState}
				activityLog={room.activityLog}
				hostPlayback={room.hostPlayback}
				voteBusyId={room.voteBusyId}
				bind:renameDisplayName={room.renameDisplayName}
				renameBusy={room.renameBusy}
				bind:renameDialogOpen={room.renameDialogOpen}
				hostTransferBusyUserId={room.hostTransferBusyUserId}
				hostTransferActionBusy={room.hostTransferActionBusy}
				hostTransferLinkBusy={room.hostTransferLinkBusy}
				providerLinkedForTransfer={room.providerLinkedForTransfer}
				onVote={room.handleVote}
				onRemove={room.handleRemove}
				onPlayback={room.handlePlayback}
				onAddTrack={room.handleAddTrack}
				onMarkActivityRead={room.markActivityRead}
				onOpenRename={room.openRenameDialog}
				onRenameSubmit={room.handleRenameSubmit}
				onOfferHostTransfer={room.handleOfferHostTransfer}
				onAcceptHostTransfer={room.handleAcceptHostTransfer}
				onRejectHostTransfer={room.handleRejectHostTransfer}
				onLinkProvider={room.linkProviderForHostTransfer}
			/>
		{:else}
			<LoadingState message="Preparing room…" />
		{/if}
	</div>
</div>
