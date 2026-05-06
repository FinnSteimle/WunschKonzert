<script lang="ts">
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import type { QueueEntryDto } from '$lib/types/api';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';

	let {
		entry,
		skipCount = 0,
		requiredVotes = 1,
		hasVoted = false,
		busy = false,
		connected = true,
		onToggleSkip
	}: {
		entry: QueueEntryDto | null;
		skipCount?: number;
		requiredVotes?: number;
		hasVoted?: boolean;
		busy?: boolean;
		connected?: boolean;
		onToggleSkip?: () => void;
	} = $props();

	const deepLink = $derived(entry?.track.deepLink?.trim() ?? '');
	const skipDisabled = $derived(!connected || busy || !entry);
</script>

{#if entry}
	<Card class="min-w-0 overflow-hidden">
		<div class="flex min-w-0 gap-3 px-4 py-0 sm:gap-4">
			{#if entry.track.coverUrl}
				<img
					src={entry.track.coverUrl}
					alt=""
					class="bg-muted size-20 shrink-0 rounded-md object-cover sm:size-24"
				/>
			{:else}
				<div
					class="bg-muted text-muted-foreground flex size-20 shrink-0 items-center justify-center rounded-md text-xs sm:size-24"
				>
					No art
				</div>
			{/if}
			<div class="min-w-0 flex-1">
				<CardHeader class="p-0 pb-1">
					<div class="flex flex-wrap items-center gap-2">
						<Badge variant="outline" class="text-[10px] uppercase">Now playing</Badge>
						{#if entry.status}
							<span class="text-muted-foreground text-xs capitalize">{entry.status}</span>
						{/if}
					</div>
					<CardTitle class="line-clamp-2 text-base sm:text-lg">{entry.track.title}</CardTitle>
					<CardDescription class="line-clamp-2">
						{entry.track.artist}
						{#if entry.track.album}
							<span class="text-muted-foreground"> · {entry.track.album}</span>
						{/if}
					</CardDescription>
				</CardHeader>
				<CardContent class="text-muted-foreground flex flex-col gap-2 p-0 text-xs">
					<p>Added by {entry.addedBy.displayName}</p>
					<div class="flex items-center gap-2">
						<Button
							type="button"
							size="sm"
							variant={hasVoted ? 'default' : 'outline'}
							class={hasVoted ? 'bg-orange-500 hover:bg-orange-500 text-white' : ''}
							disabled={skipDisabled}
							onclick={() => onToggleSkip?.()}
						>
							{hasVoted ? 'Skip voted' : 'Vote skip'}
						</Button>
						<span
							class="text-muted-foreground tabular-nums text-xs"
							aria-label="{skipCount} of {requiredVotes} votes to skip current song"
						>
							{skipCount}/{requiredVotes}
						</span>
					</div>
					{#if deepLink}
						<Button
							variant="outline"
							size="sm"
							class="w-fit"
							href={deepLink}
							target="_blank"
							rel="noopener noreferrer"
						>
							Open track
						</Button>
					{/if}
				</CardContent>
			</div>
		</div>
	</Card>
{:else}
	<EmptyState title="Nothing playing" description="Add a song to the queue to get started." />
{/if}
