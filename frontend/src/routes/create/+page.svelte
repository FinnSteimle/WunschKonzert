<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import CreateRoomForm from '$lib/components/room/forms/CreateRoomForm.svelte';

	const spotifyLinked = $derived(page.url.searchParams.get('spotify_linked') === 'true');

	function onsuccess(payload: { roomId: string; joinCode: string }) {
		void goto(resolve('/room/[roomId]', { roomId: payload.joinCode }));
	}
</script>

<svelte:head>
	<title>Create room — WunschKonzert</title>
</svelte:head>

<div class="bg-background min-h-[100dvh]">
	<div class="mx-auto flex w-full max-w-lg min-w-0 flex-col gap-8 px-4 py-8 sm:max-w-xl sm:py-12">
		<header class="flex flex-col gap-2">
			<div class="text-muted-foreground flex items-center gap-2 text-sm">
				<img src="/logo.svg" alt="WunschKonzert logo" class="h-8 w-8 shrink-0" />
				<span>WunschKonzert</span>
			</div>
			<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">Create a room</h1>
			<p class="text-muted-foreground text-sm">
				Name your session and pick Spotify or Apple Music. You can invite guests from the room.
			</p>
		</header>

		<Card class="min-w-0 shadow-sm">
			<CardHeader>
				<CardTitle>Room details</CardTitle>
				<CardDescription>We generate a short join code for you.</CardDescription>
			</CardHeader>
			<CardContent>
				<CreateRoomForm {onsuccess} {spotifyLinked} />
			</CardContent>
		</Card>
	</div>
</div>
