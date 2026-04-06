<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import { buttonVariants } from '$lib/components/ui/button';
	import InvitePanel from '$lib/components/room/invite/InvitePanel.svelte';
	import { cn } from '$lib/utils.js';

	let {
		joinCode,
		inviteUrl,
		buttonLabel = 'Invite',
		class: className
	}: {
		joinCode: string;
		inviteUrl: string;
		buttonLabel?: string;
		class?: string;
	} = $props();
</script>

<Dialog.Root>
	<Dialog.Trigger
		type="button"
		class={cn(
			buttonVariants({ variant: 'outline', size: 'default' }),
			'touch-manipulation',
			className
		)}
	>
		{buttonLabel}
	</Dialog.Trigger>
	<Dialog.Content class="max-h-full gap-4 overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Invite guests</Dialog.Title>
			<Dialog.Description>
				Share the code, link, or QR code so others can join this room.
			</Dialog.Description>
		</Dialog.Header>
		<InvitePanel {joinCode} {inviteUrl} />
	</Dialog.Content>
</Dialog.Root>
