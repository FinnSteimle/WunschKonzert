<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import { providerLabel } from '$lib/providers/constants';
	import type { HostTransferDto, RoomStateDto } from '$lib/types/api';
	import { displayNameForUser } from '$lib/stores/room';

	let {
		transfer,
		roomState,
		currentUserId,
		providerLinked = false,
		busy = false,
		linkBusy = false,
		onAccept,
		onReject,
		onLinkProvider
	}: {
		transfer: HostTransferDto;
		roomState: RoomStateDto;
		currentUserId: string;
		providerLinked?: boolean;
		busy?: boolean;
		linkBusy?: boolean;
		onAccept?: () => void;
		onReject?: () => void;
		onLinkProvider?: () => void;
	} = $props();

	const roomProviderId = $derived(roomState.room.supportedProviderId);
	const roomProviderLabel = $derived(providerLabel(roomProviderId));
	const isInvitee = $derived(transfer.toUserId === currentUserId);
	const isInviter = $derived(transfer.fromUserId === currentUserId);
	const inviteeName = $derived(displayNameForUser(roomState, transfer.toUserId));
	const inviterName = $derived(displayNameForUser(roomState, transfer.fromUserId));
	const needsProviderLink = $derived(
		isInvitee &&
			(roomProviderId === 'spotify' || roomProviderId === 'apple-music') &&
			!providerLinked
	);
	const linkButtonLabel = $derived(
		roomProviderId === 'apple-music' ? 'Link Apple Music account' : 'Link Spotify account'
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
					{roomProviderLabel} library.
				{:else}
					Waiting for {inviteeName} to accept or decline.
				{/if}
			</CardDescription>
		</CardHeader>
		{#if isInvitee}
			<CardContent class="flex flex-col gap-3 pt-0">
				{#if needsProviderLink}
					<p class="text-muted-foreground text-sm">
						Link {roomProviderLabel} before accepting. Playback runs on the new host's account.
					</p>
					<Button
						type="button"
						variant="outline"
						class="w-full min-[400px]:w-auto"
						disabled={linkBusy || busy}
						onclick={() => onLinkProvider?.()}
					>
						{linkBusy ? 'Connecting…' : linkButtonLabel}
					</Button>
				{/if}
				<div class="flex flex-col gap-2 min-[400px]:flex-row">
					<Button
						type="button"
						class="w-full min-[400px]:flex-1"
						disabled={busy || needsProviderLink}
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
