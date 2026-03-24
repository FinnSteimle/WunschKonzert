<script lang="ts">
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';

	let { inviteUrl }: { inviteUrl: string } = $props();

	const qrSrc = $derived(
		inviteUrl
			? `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(inviteUrl)}`
			: ''
	);
</script>

<Card class="min-w-0">
	<CardHeader class="pb-2">
		<CardTitle class="text-base">Scan to join</CardTitle>
		<CardDescription>Opens the join link on a phone.</CardDescription>
	</CardHeader>
	<CardContent class="flex justify-center pt-0">
		{#if inviteUrl}
			<img
				src={qrSrc}
				width="220"
				height="220"
				class="bg-background rounded-md"
				alt="QR code for room invite"
			/>
		{:else}
			<p class="text-muted-foreground text-sm">Invite link not ready yet.</p>
		{/if}
	</CardContent>
</Card>
