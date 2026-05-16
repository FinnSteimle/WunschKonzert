<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import type { HostTransferDto, RoomStateDto } from '$lib/types/api';
	import { displayNameForUser } from '$lib/stores/room';

	let {
		transfer,
		roomState,
		currentUserId,
		spotifyLinked = false,
		busy = false,
		linkBusy = false,
		onAccept,
		onReject,
		onLinkSpotify
	}: {
		transfer: HostTransferDto;
		roomState: RoomStateDto;
		currentUserId: string;
		spotifyLinked?: boolean;
		busy?: boolean;
		linkBusy?: boolean;
		onAccept?: () => void;
		onReject?: () => void;
		onLinkSpotify?: () => void;
	} = $props();

	const isInvitee = $derived(transfer.toUserId === currentUserId);
	const isInviter = $derived(transfer.fromUserId === currentUserId);
	const inviteeName = $derived(displayNameForUser(roomState, transfer.toUserId));
	const inviterName = $derived(displayNameForUser(roomState, transfer.fromUserId));
	const needsSpotify = $derived(
		isInvitee && roomState.room.supportedProviderId === 'spotify' && !spotifyLinked
	);
</script>

{#if isInvitee || isInviter}
	<Card class="border-primary/30 bg-primary/5 min-w-0">
		<CardHeader class="pb-2">
			<CardTitle class="text-base">
				{#if isInvitee}
					Host invitation
				{:else}
					Host transfer pending
				{/if}
			</CardTitle>
			<CardDescription>
				{#if isInvitee}
					{inviterName} invited you to become the room host. The queue will be mapped to your
					{roomState.room.supportedProviderId === 'spotify' ? 'Spotify' : 'music'} library.
				{:else}
					Waiting for {inviteeName} to accept or decline.
				{/if}
			</CardDescription>
		</CardHeader>
		{#if isInvitee}
			<CardContent class="flex flex-col gap-3 pt-0">
				{#if needsSpotify}
					<p class="text-muted-foreground text-sm">
						Link Spotify before accepting — playback runs on the new host's account.
					</p>
					<Button
						type="button"
						variant="outline"
						class="w-full min-[400px]:w-auto"
						disabled={linkBusy || busy}
						onclick={() => onLinkSpotify?.()}
					>
						{linkBusy ? 'Redirecting…' : 'Link Spotify account'}
					</Button>
				{/if}
				<div class="flex flex-col gap-2 min-[400px]:flex-row">
					<Button
						type="button"
						class="w-full min-[400px]:flex-1"
						disabled={busy || needsSpotify}
						onclick={() => onAccept?.()}
					>
						{busy ? 'Accepting…' : 'Accept host role'}
					</Button>
					<Button
						type="button"
						variant="outline"
						class="w-full min-[400px]:flex-1"
						disabled={busy}
						onclick={() => onReject?.()}
					>
						Decline
					</Button>
				</div>
			</CardContent>
		{/if}
	</Card>
{/if}
