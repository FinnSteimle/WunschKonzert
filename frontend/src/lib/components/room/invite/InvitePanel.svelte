<script lang="ts">
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import { Input } from '$lib/components/ui/input';
	import { Badge } from '$lib/components/ui/badge';
	import CopyToClipboardButton from '$lib/components/room/invite/CopyToClipboardButton.svelte';
	import QRCodeCard from '$lib/components/room/invite/QRCodeCard.svelte';

	let {
		joinCode,
		inviteUrl
	}: {
		joinCode: string;
		inviteUrl: string;
	} = $props();
</script>

<div class="flex w-full min-w-0 flex-col gap-4">
	<Card class="min-w-0">
		<CardHeader class="pb-2">
			<CardTitle class="text-base">Room code</CardTitle>
			<CardDescription>Share this code so others can join manually.</CardDescription>
		</CardHeader>
		<CardContent class="flex flex-col gap-3 sm:flex-row sm:items-center">
			<Badge variant="secondary" class="font-mono text-lg tracking-widest">{joinCode}</Badge>
			<CopyToClipboardButton
				textToCopy={joinCode}
				label="Copy code"
				variant="outline"
				size="sm"
				class="shrink-0"
			/>
		</CardContent>
	</Card>

	<Card class="min-w-0">
		<CardHeader class="pb-2">
			<CardTitle class="text-base">Invite link</CardTitle>
			<CardDescription>Send this link — guests join in one tap.</CardDescription>
		</CardHeader>
		<CardContent class="flex flex-col gap-2">
			<div class="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-stretch">
				<Input class="min-w-0 font-mono text-xs sm:text-sm" readonly value={inviteUrl} />
				<CopyToClipboardButton
					textToCopy={inviteUrl}
					label="Copy link"
					variant="outline"
					class="shrink-0 sm:w-auto"
				/>
			</div>
		</CardContent>
	</Card>

	<QRCodeCard {inviteUrl} />
</div>
