<script lang="ts">
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';

	let { inviteUrl }: { inviteUrl: string } = $props();

	let qrDataUrl = $state('');

	$effect(() => {
		const url = inviteUrl;
		if (!url) {
			qrDataUrl = '';
			return;
		}

		qrDataUrl = '';
		let cancelled = false;

		void (async () => {
			try {
				const { default: QRCode } = await import('qrcode');
				const dataUrl = await QRCode.toDataURL(url, { width: 220, margin: 1 });
				if (!cancelled) qrDataUrl = dataUrl;
			} catch {
				if (!cancelled) qrDataUrl = '';
			}
		})();

		return () => {
			cancelled = true;
		};
	});
</script>

<Card class="min-w-0">
	<CardHeader class="pb-2">
		<CardTitle class="text-base">Scan to join</CardTitle>
		<CardDescription>Opens the join link on a phone.</CardDescription>
	</CardHeader>
	<CardContent class="flex justify-center pt-0">
		{#if inviteUrl}
			{#if qrDataUrl}
				<img
					src={qrDataUrl}
					width="220"
					height="220"
					class="bg-background"
					alt="QR code for room invite"
				/>
			{:else}
				<div
					class="bg-background h-[220px] w-[220px] shrink-0 rounded-md"
					role="status"
					aria-live="polite"
					aria-label="Generating QR code"
				></div>
			{/if}
		{:else}
			<p class="text-muted-foreground text-sm">Invite link not ready yet.</p>
		{/if}
	</CardContent>
</Card>
