<script lang="ts">
	import { getPersonalVoteState } from '$lib/stores/room';
	import type { QueueEntryDto, VoteRequest } from '$lib/types/api';
	import QueueItem from './QueueItem.svelte';
	import EmptyState from './EmptyState.svelte';

	let {
		entries,
		userId,
		voteBusyId,
		onVote
	}: {
		entries: QueueEntryDto[];
		userId: string;
		voteBusyId: string | null;
		onVote?: (queueEntryId: string, vote: VoteRequest['vote_type']) => void;
	} = $props();
</script>

{#if entries.length === 0}
	<EmptyState title="Queue is empty" description="Search for a song and add it to the queue." />
{:else}
	<ul class="flex flex-col gap-2" aria-label="Playback queue">
		{#each entries as entry (entry.queueEntryId)}
			<QueueItem
				{entry}
				personalVote={getPersonalVoteState(entry, userId)}
				{voteBusyId}
				{onVote}
			/>
		{/each}
	</ul>
{/if}
