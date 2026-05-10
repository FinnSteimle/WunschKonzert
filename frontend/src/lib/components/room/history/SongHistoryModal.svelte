<script lang="ts">
	import type { PlaybackHistoryEntryDto, RoomStateDto, TrackDto } from '$lib/types/api';
	import * as Dialog from '$lib/components/ui/dialog';
	import { buttonVariants } from '$lib/components/ui/button';
	import { cn } from '$lib/utils.js';
	import { activeQueuedTrackIds } from '$lib/stores/room';
	import HistoryItem from './HistoryItem.svelte';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';
	import { toast } from 'svelte-sonner';

	let {
		roomState,
		onAddTrack
	}: {
		roomState: RoomStateDto | null;
		onAddTrack?: (track: TrackDto) => Promise<void> | void;
	} = $props();

	let open = $state(false);
	let addingTrackId = $state<string | null>(null);

	const queuedTrackIds = $derived(activeQueuedTrackIds(roomState));

	async function readdTrack(track: TrackDto) {
		addingTrackId = track.trackId;
		try {
			if (!onAddTrack) {
				throw new Error('Add action unavailable');
			}
			await onAddTrack(track);
			toast.success('Added to queue');
		} catch (err) {
			const msg = err instanceof Error ? err.message : 'Could not add song';
			if (msg === 'Song is already in the queue') {
				toast.message(msg);
			} else {
				toast.error(msg);
			}
		} finally {
			addingTrackId = null;
		}
	}

	const historyRows = $derived.by((): PlaybackHistoryEntryDto[] => {
		const raw = roomState?.history ?? [];
		return [...raw].sort(
			(a, b) => new Date(b.playedAt).getTime() - new Date(a.playedAt).getTime()
		);
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
				Recent songs played in this room.
			</Dialog.Description>
		</Dialog.Header>
		<div class="max-h-[60vh] overflow-y-auto">
			{#if historyRows.length === 0}
				<EmptyState
					title="No songs played yet"
					description="Songs will appear here once they finish playing."
				/>
			{:else}
				<ul class="flex flex-col gap-2" aria-label="Song history">
					{#each historyRows as row (row.historyId)}
						<li
							class="border-border rounded-lg border bg-card px-3 py-3 {queuedTrackIds.has(
								row.track.trackId
							)
								? 'bg-muted/45 border-muted-foreground/20'
								: ''}"
						>
							<HistoryItem
								track={row.track}
								playedAt={row.playedAt}
								inQueue={queuedTrackIds.has(row.track.trackId)}
								adding={addingTrackId === row.track.trackId}
								onAdd={onAddTrack ? () => void readdTrack(row.track) : undefined}
							/>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</Dialog.Content>
</Dialog.Root>
