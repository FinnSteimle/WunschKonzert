<script lang="ts">
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import DisplayNameInput from '$lib/components/room/forms/DisplayNameInput.svelte';

	type Props = {
		joinCode: string;
		displayName: string;
		busy: boolean;
		error: string | null;
		onConfirm: () => void;
	};

	let {
		joinCode,
		displayName = $bindable(),
		busy,
		error,
		onConfirm
	}: Props = $props();
</script>

<Card class="mx-auto w-full max-w-md">
	<CardHeader>
		<CardTitle>Join room</CardTitle>
		<CardDescription>
			You opened a room link. Choose how your name appears to others.
		</CardDescription>
		<p class="text-muted-foreground font-mono text-sm tracking-wide">
			Code {joinCode}
		</p>
	</CardHeader>
	<CardContent class="flex flex-col gap-4">
		<DisplayNameInput
			id="wk-link-join-display"
			bind:value={displayName}
			disabled={busy}
			maxlength={60}
		/>
		{#if error}
			<p class="text-destructive text-sm">{error}</p>
		{/if}
		<div class="flex flex-col gap-2 min-[400px]:flex-row min-[400px]:flex-wrap">
			<Button
				type="button"
				class="w-full min-[400px]:w-auto"
				disabled={busy}
				onclick={() => onConfirm()}
			>
				{busy ? 'Joining…' : 'Join room'}
			</Button>
			<Button variant="outline" href="/" class="w-full min-[400px]:w-auto">Back home</Button>
		</div>
	</CardContent>
</Card>
