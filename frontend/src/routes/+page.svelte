<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import RoomCodeJoinForm from '$lib/components/room/forms/RoomCodeJoinForm.svelte';
	import RecentRoomsPanel from '$lib/components/home/RecentRoomsPanel.svelte';
</script>

<svelte:head>
	<title>WunschKonzert — Join a room</title>
</svelte:head>

<div class="bg-background min-h-[100dvh]">
	<div class="mx-auto flex w-full max-w-lg min-w-0 flex-col gap-8 px-4 py-8 sm:py-12">
		<header class="flex flex-col gap-2 text-center sm:text-left">
			<div class="flex items-center justify-center gap-3 sm:justify-start">
				<img
					src="/logo.svg"
					alt="WunschKonzert logo"
					class="h-10 w-10 sm:h-12 sm:w-12"
				/>
				<h1 class="text-3xl font-semibold tracking-tight sm:text-4xl">WunschKonzert</h1>
			</div>
			<p class="text-muted-foreground text-sm sm:text-base">
				Join a listening room with a code, or start your own and share the link.
			</p>
		</header>

		<RecentRoomsPanel />

		<Card class="min-w-0 shadow-sm">
			<CardHeader>
				<CardTitle>Join with code</CardTitle>
				<CardDescription>Enter the 6-character code from the host.</CardDescription>
			</CardHeader>
			<CardContent>
				<RoomCodeJoinForm />
			</CardContent>
		</Card>

		<div class="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
			<p class="text-muted-foreground text-center text-sm sm:text-left">Hosting a session?</p>
			<Button href="/create" class="w-full sm:w-auto">Create a room</Button>
		</div>
	</div>
</div>
