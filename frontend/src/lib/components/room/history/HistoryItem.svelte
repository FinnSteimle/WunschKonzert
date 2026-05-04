<script lang="ts">
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import type { QueueEntryDto } from '$lib/types/api';

	let {
		entry,
		inQueue = false,
		adding = false,
		onAdd
	}: {
		entry: QueueEntryDto;
		inQueue?: boolean;
		adding?: boolean;
		onAdd?: () => void;
	} = $props();

	function formatPlayedAgo(isoString: string): string {
		const date = new Date(isoString);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);

		if (diffMins < 1) return 'just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
		return date.toLocaleDateString();
	}
</script>

<div class="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center">
	<div class="flex min-w-0 flex-1 gap-3">
		{#if entry.track.coverUrl}
			<img
				src={entry.track.coverUrl}
				alt=""
				class="bg-muted size-14 shrink-0 rounded-md object-cover sm:size-16"
			/>
		{:else}
			<div
				class="bg-muted text-muted-foreground flex size-14 shrink-0 items-center justify-center rounded-md text-[10px] sm:size-16"
			>
				No art
			</div>
		{/if}
		<div class="min-w-0 flex-1">
			<p class="line-clamp-2 text-sm font-medium">{entry.track.title}</p>
			<p class="text-muted-foreground line-clamp-1 text-xs">{entry.track.artist}</p>
			<p class="text-muted-foreground mt-1 text-[11px]">Added by {entry.addedBy.displayName}</p>
			<p class="text-muted-foreground mt-1 text-[11px]">
				{#if entry.playedAt}
					Played {formatPlayedAgo(entry.playedAt)}
				{:else}
					Played
				{/if}
			</p>
		</div>
	</div>
	<div class="flex shrink-0 flex-wrap items-center justify-end gap-2 sm:flex-col sm:items-end">
		{#if inQueue}
			<Badge variant="secondary" class="shrink-0">In queue</Badge>
		{/if}
		<Button
			type="button"
			size="sm"
			class="w-full gap-2 sm:w-auto"
			disabled={inQueue || adding || !onAdd}
			title={inQueue ? 'This song is already in the queue' : undefined}
			aria-label={inQueue ? 'Already in queue' : 'Add to queue again'}
			onclick={() => onAdd?.()}
		>
			<PlusIcon class="size-4" aria-hidden="true" />
			{adding ? 'Adding…' : 'Add again'}
		</Button>
	</div>
</div>
