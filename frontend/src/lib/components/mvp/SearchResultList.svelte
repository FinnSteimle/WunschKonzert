<script lang="ts">
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { Button } from '$lib/components/ui/button';
	import type { TrackDto } from '$lib/types/api';
	import EmptyState from './EmptyState.svelte';

	let {
		tracks,
		addingTrackId,
		onAdd
	}: {
		tracks: TrackDto[];
		addingTrackId: string | null;
		onAdd?: (track: TrackDto) => void;
	} = $props();
</script>

{#if tracks.length === 0}
	<EmptyState title="No results" description="Try another search." />
{:else}
	<ul class="flex max-h-[min(24rem,55vh)] flex-col gap-2 overflow-y-auto pr-1" aria-label="Search results">
		{#each tracks as track (track.trackId)}
			<li
				class="border-border flex min-w-0 flex-col gap-2 rounded-lg border bg-card p-3 sm:flex-row sm:items-center"
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
					<p class="line-clamp-2 text-sm font-medium">{track.title}</p>
					<p class="text-muted-foreground line-clamp-2 text-xs">{track.artist}</p>
				</div>
				<Button
					type="button"
					size="sm"
					class="w-full shrink-0 gap-2 sm:w-auto"
					disabled={addingTrackId === track.trackId}
					onclick={() => onAdd?.(track)}
				>
					<PlusIcon class="size-4" aria-hidden="true" />
					{addingTrackId === track.trackId ? 'Adding…' : 'Add'}
				</Button>
			</li>
		{/each}
	</ul>
{/if}
