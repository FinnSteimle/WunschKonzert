<script lang="ts">
	import RotateCcwIcon from '@lucide/svelte/icons/rotate-ccw';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import type { ReplayVoteStateDto } from '$lib/types/api';
	import { replayMajorityThreshold } from '$lib/stores/room';

	let {
		replayVote,
		userId,
		connected,
		busy,
		onVote,
		onRetract
	}: {
		replayVote: ReplayVoteStateDto;
		userId: string;
		connected: boolean;
		busy: boolean;
		onVote?: () => void;
		onRetract?: () => void;
	} = $props();

	const needed = $derived(replayMajorityThreshold(replayVote.activeUserCount));
	const hasVoted = $derived(replayVote.voterUserIds.includes(userId));
	let nowMs = $state(Date.now());

	$effect(() => {
		if (replayVote.status !== 'open') return;
		const id = setInterval(() => {
			nowMs = Date.now();
		}, 1000);
		return () => clearInterval(id);
	});

	const closesAtMs = $derived(new Date(replayVote.closesAt).getTime());
	const isPastDeadline = $derived(nowMs > closesAtMs);
	const windowOpen = $derived(replayVote.status === 'open' && !isPastDeadline);

	const closingLine = $derived.by(() => {
		if (!Number.isFinite(closesAtMs)) return 'Voting closes when the current track ends.';
		const sec = Math.max(0, Math.round((closesAtMs - nowMs) / 1000));
		if (sec <= 0) return 'Voting has closed.';
		if (sec < 60) return `Closes in ${sec}s`;
		const m = Math.floor(sec / 60);
		const s = sec % 60;
		return `Closes in ${m}m ${s.toString().padStart(2, '0')}s`;
	});

	const headline = $derived.by(() => {
		if (replayVote.status === 'met') return 'Replay scheduled';
		if (replayVote.status === 'expired' || isPastDeadline) return 'Replay vote closed';
		return 'Replay last track';
	});

	const detailLine = $derived.by(() => {
		if (replayVote.status === 'met') {
			return 'This song will play again soon — it was added to the top of the queue.';
		}
		if (replayVote.status === 'expired' || isPastDeadline) {
			return 'The voting window for this track has ended.';
		}
		return 'If enough listeners vote before the window closes, this track is added to the top of the queue again.';
	});
</script>

<Card class="border-muted min-w-0 overflow-hidden">
	<CardHeader class="pb-2">
		<div class="flex flex-wrap items-center gap-2">
			<RotateCcwIcon class="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
			<CardTitle class="text-base">{headline}</CardTitle>
			{#if hasVoted && windowOpen}
				<Badge variant="secondary" class="text-[10px] uppercase">Your vote counted</Badge>
			{/if}
		</div>
		<CardDescription class="line-clamp-2 font-medium text-foreground/90">
			{replayVote.track.title}
			<span class="text-muted-foreground"> · {replayVote.track.artist}</span>
		</CardDescription>
	</CardHeader>
	<CardContent class="flex flex-col gap-3 text-sm">
		<p class="text-muted-foreground leading-snug">{detailLine}</p>
		{#if replayVote.status === 'open' && !isPastDeadline}
			<div
				class="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
				aria-live="polite"
			>
				<span class="font-mono tabular-nums"
					>{replayVote.voteCount} / {needed} for majority</span
				>
				<span aria-hidden="true">·</span>
				<span>{closingLine}</span>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button
					type="button"
					size="sm"
					disabled={!connected || busy || hasVoted}
					class="min-w-[7rem]"
					onclick={() => onVote?.()}
				>
					{busy ? 'Sending…' : hasVoted ? 'Voted' : 'Vote to replay'}
				</Button>
				{#if hasVoted}
					<Button
						type="button"
						size="sm"
						variant="outline"
						disabled={!connected || busy}
						onclick={() => onRetract?.()}
					>
						Remove vote
					</Button>
				{/if}
			</div>
		{/if}
	</CardContent>
</Card>
