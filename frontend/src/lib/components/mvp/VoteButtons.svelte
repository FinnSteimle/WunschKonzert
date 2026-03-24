<script lang="ts">
	import ThumbsDownIcon from '@lucide/svelte/icons/thumbs-down';
	import ThumbsUpIcon from '@lucide/svelte/icons/thumbs-up';
	import { Button } from '$lib/components/ui/button';
	import type { VoteRequest } from '$lib/types/api';

	let {
		state,
		disabled = false,
		busy = false,
		onVote
	}: {
		state: 'upvote' | 'downvote' | 'neutral';
		disabled?: boolean;
		busy?: boolean;
		onVote?: (vote: VoteRequest['vote_type']) => void;
	} = $props();

	function pick(next: VoteRequest['vote_type']) {
		if (disabled || busy) return;
		onVote?.(next);
	}
</script>

<div class="flex items-center gap-1">
	<Button
		type="button"
		variant={state === 'upvote' ? 'default' : 'ghost'}
		size="icon-sm"
		class="size-8"
		aria-pressed={state === 'upvote'}
		aria-label="Upvote"
		disabled={disabled || busy}
		onclick={() => pick(state === 'upvote' ? 'neutral' : 'upvote')}
	>
		<ThumbsUpIcon class="size-4" />
	</Button>
	<Button
		type="button"
		variant={state === 'downvote' ? 'destructive' : 'ghost'}
		size="icon-sm"
		class="size-8"
		aria-pressed={state === 'downvote'}
		aria-label="Downvote"
		disabled={disabled || busy}
		onclick={() => pick(state === 'downvote' ? 'neutral' : 'downvote')}
	>
		<ThumbsDownIcon class="size-4" />
	</Button>
</div>
