<script lang="ts">
	import ThumbsDownIcon from '@lucide/svelte/icons/thumbs-down';
	import ThumbsUpIcon from '@lucide/svelte/icons/thumbs-up';
	import { Button } from '$lib/components/ui/button';
	import type { VoteRequest } from '$lib/types/api';

	let {
		state,
		upvotes,
		downvotes,
		disabled = false,
		busy = false,
		onVote
	}: {
		state: 'upvote' | 'downvote' | 'neutral';
		upvotes: number;
		downvotes: number;
		disabled?: boolean;
		busy?: boolean;
		onVote?: (vote: VoteRequest['vote_type']) => void;
	} = $props();

	function pick(next: VoteRequest['vote_type']) {
		if (disabled || busy) return;
		onVote?.(next);
	}
</script>

<div class="flex items-start gap-2">
	<div class="flex flex-col items-center gap-1">
		<Button
			type="button"
			variant={state === 'upvote' ? 'default' : 'outline'}
			size="icon-sm"
			class="size-8 rounded-full shadow-sm {state === 'upvote' ? 'bg-emerald-600 text-white' : ''}"
			aria-pressed={state === 'upvote'}
			aria-label="Upvote"
			disabled={disabled || busy}
			onclick={() => pick(state === 'upvote' ? 'neutral' : 'upvote')}
		>
			<ThumbsUpIcon class="size-4" />
		</Button>
		<span class="text-emerald-600 text-xs tabular-nums" aria-label="Upvotes">+{upvotes}</span>
	</div>
	<div class="flex flex-col items-center gap-1">
		<Button
			type="button"
			variant={state === 'downvote' ? 'destructive' : 'outline'}
			size="icon-sm"
			class="size-8 rounded-full shadow-sm"
			aria-pressed={state === 'downvote'}
			aria-label="Downvote"
			disabled={disabled || busy}
			onclick={() => pick(state === 'downvote' ? 'neutral' : 'downvote')}
		>
			<ThumbsDownIcon class="size-4" />
		</Button>
		<span class="text-red-600 text-xs tabular-nums" aria-label="Downvotes">-{downvotes}</span>
	</div>
</div>
