<script lang="ts">
	import { getPersonalVoteState } from '$lib/stores/room';
	import type { QueueEntryDto, VoteRequest } from '$lib/types/api';
	import QueueItem from '$lib/components/room/queue/QueueItem.svelte';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';
	import { flip } from 'svelte/animate';

	let {
		entries,
		userId,
		hostId,
		totalMembers,
		voteBusyId,
		onVote,
		onRemove
	}: {
		entries: QueueEntryDto[];
		userId: string;
		hostId: string;
		totalMembers: number;
		voteBusyId: string | null;
		onVote?: (queueEntryId: string, vote: VoteRequest['vote_type']) => void;
		onRemove?: (queueEntryId: string) => void;
	} = $props();

	/** Show only unplayed songs sorted by votes (tie-break on position). */
	const sortedEntries = $derived.by(() => {
		return entries
			.filter((e) => e.status !== 'played')
			.sort((a, b) =>
				b.voteScore !== a.voteScore ? b.voteScore - a.voteScore : a.position - b.position
			);
	});
</script>

{#if sortedEntries.length === 0}
	<EmptyState title="Queue is empty" description="Search for a song and add it to the queue." />
{:else}
	<ul class="flex flex-col gap-2" aria-label="Playback queue">
		{#each sortedEntries as entry (entry.queueEntryId)}
			<li
				animate:flip={{ duration: 300 }}
				class="border-border flex min-w-0 flex-col gap-2 rounded-lg border bg-card px-3 py-3 sm:flex-row sm:items-center sm:gap-3"
			>
				<QueueItem
					{entry}
					personalVote={getPersonalVoteState(entry, userId)}
					{voteBusyId}
					currentUserId={userId}
					{hostId}
					{totalMembers}
					{onVote}
					{onRemove}
				/>
			</li>
		{/each}
	</ul>
{/if}
