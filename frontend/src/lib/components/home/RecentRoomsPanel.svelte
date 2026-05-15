<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { resolve } from '$app/paths';
	import { Badge } from '$lib/components/ui/badge';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import {
		getRecentRooms,
		syncRecentRoomsAvailability,
		type RecentRoomEntry
	} from '$lib/session/recentRooms';

	let entries = $state<RecentRoomEntry[]>([]);
	let intervalId: number;

	// Check availability every 5 minutes (300,000 ms)
	const CHECK_INTERVAL = 300000;

	onMount(() => {
		if (browser) {
			entries = getRecentRooms();
			syncAvailability();

			// Set up periodic checking
			intervalId = window.setInterval(syncAvailability, CHECK_INTERVAL);
		}
	});

	onDestroy(() => {
		if (browser && intervalId) {
			clearInterval(intervalId);
		}
	});

	async function syncAvailability() {
		const nextEntries = await syncRecentRoomsAvailability();
		entries = nextEntries;
	}
</script>

{#if entries.length > 0}
	<Card class="min-w-0 shadow-sm">
		<CardHeader>
			<CardTitle>Recent rooms</CardTitle>
			<CardDescription>Jump back to a room you hosted or joined on this device.</CardDescription>
		</CardHeader>
		<CardContent class="flex flex-col gap-1">
			{#each entries as r (r.joinCode)}
				<a
					href={resolve('/room/[roomId]', { roomId: r.joinCode })}
					class="border-border hover:bg-accent/50 flex flex-wrap items-center gap-2 rounded-md border px-3 py-2.5 text-sm transition-colors"
				>
					<span class="min-w-0 flex-1 truncate font-medium">{r.name}</span>
					<div class="flex shrink-0 items-center gap-2">
						{#if r.isHost}
							<Badge variant="secondary">Host</Badge>
						{/if}
						<span class="text-muted-foreground font-mono text-xs tracking-wide">{r.joinCode}</span>
					</div>
				</a>
			{/each}
		</CardContent>
	</Card>
{/if}
