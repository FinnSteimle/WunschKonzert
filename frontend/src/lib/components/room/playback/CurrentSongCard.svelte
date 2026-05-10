<script lang="ts">
	import RotateCcwIcon from '@lucide/svelte/icons/rotate-ccw';
	import SkipForwardIcon from '@lucide/svelte/icons/skip-forward';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import type { QueueEntryDto, ReplayVoteStatus } from '$lib/types/api';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';

	let {
		entry,
		skipCount = 0,
		requiredVotes = 1,
		hasSkipVoted = false,
		busy = false,
		onToggleSkip,
		replay
	}: {
		entry: QueueEntryDto | null;
		skipCount?: number;
		requiredVotes?: number;
		hasSkipVoted?: boolean;
		busy?: boolean;
		onToggleSkip?: () => void;
		replay?: {
			voteCount: number;
			neededVotes: number;
			hasVoted: boolean;
			status: ReplayVoteStatus;
			closesAt: string;
			onToggle: () => void;
		};
	} = $props();

	let nowMs = $state(Date.now());

	$effect(() => {
		if (!replay || replay.status !== 'open') return;
		const id = setInterval(() => {
			nowMs = Date.now();
		}, 1000);
		return () => clearInterval(id);
	});

	const replayClosesAtMs = $derived(replay ? new Date(replay.closesAt).getTime() : NaN);

	const replayWindowOpen = $derived.by(() => {
		if (!replay || replay.status !== 'open') return false;
		if (!Number.isFinite(replayClosesAtMs)) return true;
		return nowMs <= replayClosesAtMs;
	});

	const deepLink = $derived(entry?.track.deepLink?.trim() ?? '');
	/** Do not tie to WS "connected": store can briefly disagree with socket.readyState → dead clicks */
	const skipDisabled = $derived(busy || !entry);

	const replayDisabled = $derived(
		busy || !entry || !replay || replay.status === 'met' || replay.status === 'expired' || !replayWindowOpen
	);

	const skipLabel = $derived(`Skip (${skipCount}/${requiredVotes})`);
	const replayLabel = $derived(
		replay ? `Replay (${replay.voteCount}/${replay.neededVotes})` : ''
	);
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
					<div class="flex flex-wrap items-center gap-1.5" aria-label="Playback votes">
						{#if replay}
							<Button
								type="button"
								variant="outline"
								size="sm"
								class="text-muted-foreground h-8 min-h-8 gap-1 rounded-md px-2 py-0 {replay.hasVoted
									? 'border-emerald-500/60 bg-emerald-500/15'
									: ''}"
								disabled={replayDisabled}
								aria-label={replayLabel}
								title="Replay votes while this track plays"
								onclick={() => replay.onToggle()}
							>
								<RotateCcwIcon class="size-3.5 shrink-0" aria-hidden="true" />
								<span class="tabular-nums text-[10px] leading-none font-medium">
									{replay.voteCount}/{replay.neededVotes}
								</span>
							</Button>
						{/if}
						<Button
							type="button"
							variant="outline"
							size="sm"
							class="text-muted-foreground h-8 min-h-8 gap-1 rounded-md px-2 py-0 {hasSkipVoted
								? 'border-orange-500 bg-orange-500 text-white hover:bg-orange-500 hover:text-white'
								: ''}"
							disabled={skipDisabled}
							aria-label={skipLabel}
							title="Vote to skip this track"
							onclick={() => onToggleSkip?.()}
						>
							<SkipForwardIcon class="size-3.5 shrink-0" aria-hidden="true" />
							<span class="tabular-nums text-[10px] leading-none font-medium">
								{skipCount}/{requiredVotes}
							</span>
						</Button>
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
