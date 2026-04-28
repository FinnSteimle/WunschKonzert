<script lang="ts">
	import type { RoomStateDto } from '$lib/types/api';
	import * as Dialog from '$lib/components/ui/dialog';
	import { buttonVariants } from '$lib/components/ui/button';
	import { cn } from '$lib/utils.js';
	import HistoryItem from './HistoryItem.svelte';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';

	let { roomState }: { roomState: RoomStateDto | null } = $props();

	let open = $state(false);

	const playedSongs = $derived.by(() => {
		if (!roomState?.queue) return [];

		return roomState.queue
			.filter((entry) => entry.status === 'played')
			.sort((a, b) => new Date(b.queuedAt).getTime() - new Date(a.queuedAt).getTime())
			.slice(0, 30);
	});
</script>

<Dialog.Root bind:open>
	<Dialog.Trigger
		type="button"
		class={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'touch-manipulation')}
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="16"
			height="16"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			class="mr-2"
		>
			<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
			<path d="M3 3v5h5" />
		</svg>
		History
	</Dialog.Trigger>
	<Dialog.Content class="max-w-2xl">
		<Dialog.Header>
			<Dialog.Title>Song History</Dialog.Title>
			<Dialog.Description>
				View the last 30 songs that have been played in this room.
			</Dialog.Description>
		</Dialog.Header>
		<div class="max-h-[60vh] overflow-y-auto">
			{#if playedSongs.length === 0}
				<EmptyState
					title="No songs played yet"
					description="Songs will appear here once they finish playing."
				/>
			{:else}
				<ul class="flex flex-col gap-2" aria-label="Song history">
					{#each playedSongs as entry (entry.queueEntryId)}
						<li class="border-border rounded-lg border bg-card px-3 py-3">
							<HistoryItem {entry} />
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</Dialog.Content>
</Dialog.Root>
