<script lang="ts">
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import CreateRoomForm from '$lib/components/mvp/CreateRoomForm.svelte';
	import InvitePanelDialog from '$lib/components/mvp/InvitePanelDialog.svelte';
	import { browser } from '$app/environment';

	let created = $state<{ roomId: string; joinCode: string } | null>(null);

	const inviteUrl = $derived.by(() => {
		if (!created || !browser) return '';
		const origin = page.url.origin;
		return `${origin}/join/${created.joinCode}`;
	});

	function onsuccess(payload: { roomId: string; joinCode: string }) {
		created = payload;
	}
</script>

<svelte:head>
	<title>Create room — WunschKonzert</title>
</svelte:head>

<div class="bg-background min-h-[100dvh]">
	<div class="mx-auto flex w-full max-w-lg min-w-0 flex-col gap-8 px-4 py-8 sm:max-w-xl sm:py-12">
		<header class="flex flex-col gap-2">
			<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">Create a room</h1>
			<p class="text-muted-foreground text-sm">
				Name your session, pick Spotify, and share the code or link.
			</p>
		</header>

		{#if !created}
			<Card class="min-w-0 shadow-sm">
				<CardHeader>
					<CardTitle>Room details</CardTitle>
					<CardDescription>We generate a short join code for you.</CardDescription>
				</CardHeader>
				<CardContent>
					<CreateRoomForm {onsuccess} />
				</CardContent>
			</Card>
		{:else}
			<div class="flex flex-col gap-2 min-[400px]:flex-row">
				<InvitePanelDialog
					joinCode={created.joinCode}
					inviteUrl={inviteUrl}
					class="w-full flex-1"
				/>
				<Button href={`/room/${created.roomId}`} class="w-full flex-1">Open room</Button>
				<Button variant="outline" href="/" class="w-full flex-1">Back home</Button>
			</div>
		{/if}
	</div>
</div>
