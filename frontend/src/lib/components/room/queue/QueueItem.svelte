<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import type { QueueEntryDto, VoteRequest } from '$lib/types/api';
	import VoteButtons from '$lib/components/room/queue/VoteButtons.svelte';
	import RemoveButton from '$lib/components/room/queue/RemoveButton.svelte';

	let {
		entry,
		personalVote,
		voteBusyId,
		currentUserId,
		hostId,
		totalMembers,
		onVote,
		onRemove
	}: {
		entry: QueueEntryDto;
		personalVote: 'upvote' | 'downvote' | 'neutral';
		voteBusyId: string | null;
		currentUserId: string;
		hostId: string;
		totalMembers: number;
		onVote?: (queueEntryId: string, vote: VoteRequest['vote_type']) => void;
		onRemove?: (queueEntryId: string) => void;
	} = $props();

	const upvotes = $derived(entry.feedback.filter((f) => f.type === 'upvote').length);
	const downvotes = $derived(entry.feedback.filter((f) => f.type === 'downvote').length);
	const busy = $derived(voteBusyId === entry.queueEntryId);

	// Remove button derived state
	const canRemoveDirectly = $derived(
		currentUserId === entry.addedBy.userId || currentUserId === hostId
	);
	const skipVotes = $derived(entry.feedback.filter((f) => f.type === 'skip'));
	const skipCount = $derived(skipVotes.length);
	const requiredVotes = $derived(Math.ceil(Math.max(1, totalMembers - 1) * 0.5));
	const hasVoted = $derived(skipVotes.some((f) => f.userId === currentUserId));
</script>

<div class="flex min-w-0 flex-1 gap-3 sm:items-center">
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
		<p class="text-muted-foreground mt-1 text-[11px]">by {entry.addedBy.displayName}</p>
		<div class="mt-2 flex flex-wrap items-center gap-2">
			<Badge variant="secondary" class="text-sm tabular-nums">Score {entry.voteScore}</Badge>
			{#if entry.status}
				<Badge variant="outline" class="text-[10px] capitalize">{entry.status}</Badge>
			{/if}
		</div>
	</div>
</div>
<div class="flex items-start gap-2">
	<VoteButtons
		state={personalVote}
		{upvotes}
		{downvotes}
		{busy}
		onVote={(v) => onVote?.(entry.queueEntryId, v)}
	/>
	<RemoveButton
		{canRemoveDirectly}
		{skipCount}
		{requiredVotes}
		{hasVoted}
		{busy}
		onRemove={() => onRemove?.(entry.queueEntryId)}
	/>
</div>
