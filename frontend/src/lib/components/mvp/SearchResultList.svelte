<script lang="ts">
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import type { TrackDto } from '$lib/types/api';
	import EmptyState from './EmptyState.svelte';

	let {
		tracks,
		addingTrackId,
		queuedTrackIds,
		onAdd
	}: {
		tracks: TrackDto[];
		addingTrackId: string | null;
		queuedTrackIds?: ReadonlySet<string>;
		onAdd?: (track: TrackDto) => void;
	} = $props();
</script>

{#if tracks.length === 0}
	<EmptyState title="No results" description="Try another search." />
{:else}
	<ul class="flex max-h-[min(24rem,55vh)] flex-col gap-2 overflow-y-auto pr-1" aria-label="Search results">
		{#each tracks as track (track.trackId)}
			{@const inQueue = !!queuedTrackIds?.has(track.trackId)}
			<li
				class="border-border flex min-w-0 flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center {inQueue
					? 'bg-muted/45 border-muted-foreground/20'
					: 'bg-card'}"
			>
				{#if track.coverUrl}
					<img
						src={track.coverUrl}
						alt=""
						class="bg-muted mx-auto size-14 shrink-0 rounded object-cover sm:mx-0"
					/>
				{:else}
					<div
						class="bg-muted text-muted-foreground mx-auto flex size-14 shrink-0 items-center justify-center rounded text-[10px] sm:mx-0"
					>
						No art
					</div>
				{/if}
				<div class="min-w-0 flex-1 text-center sm:text-start">
					<div
						class="flex flex-wrap items-center justify-center gap-2 sm:justify-start"
					>
						<p class="line-clamp-2 text-sm font-medium">{track.title}</p>
						{#if inQueue}
							<Badge variant="secondary" class="shrink-0">In queue</Badge>
						{/if}
					</div>
					<p class="text-muted-foreground line-clamp-2 text-xs">{track.artist}</p>
				</div>
				<Button
					type="button"
					size="sm"
					class="w-full shrink-0 gap-2 sm:w-auto"
					disabled={inQueue || addingTrackId === track.trackId}
					title={inQueue ? 'This song is already in the queue' : undefined}
					aria-label={inQueue ? 'Already in queue' : 'Add to queue'}
					onclick={() => onAdd?.(track)}
				>
					<PlusIcon class="size-4" aria-hidden="true" />
					{addingTrackId === track.trackId ? 'Adding…' : 'Add'}
				</Button>
			</li>
		{/each}
	</ul>
{/if}
