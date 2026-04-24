<script lang="ts">
	import ThumbsDownIcon from '@lucide/svelte/icons/thumbs-down';
	import ThumbsUpIcon from '@lucide/svelte/icons/thumbs-up';
	import { Button } from '$lib/components/ui/button';
	import type { VoteRequest } from '$lib/types/api';

	let {
		state: voteState,
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

	let upBounce = $state(false);
	let downBounce = $state(false);

	function triggerBounce(type: VoteRequest['vote_type']) {
		if (type === 'neutral') return;
		if (type === 'upvote') upBounce = true;
		if (type === 'downvote') downBounce = true;
	}

	function handlePress(type: VoteRequest['vote_type']) {
		if (disabled || busy) return;
		triggerBounce(type);
	}

	function pick(next: VoteRequest['vote_type']) {
		if (disabled || busy) return;
		triggerBounce(next);
		onVote?.(next);
	}
</script>

<div class="flex items-start gap-2">
	<div class="flex flex-col items-center gap-1">
		<Button
			type="button"
			variant={voteState === 'upvote' ? 'default' : 'outline'}
			size="icon-sm"
			class="vote-button size-8 rounded-full shadow-sm transition-all duration-150 ease-out {voteState ===
			'upvote'
				? 'bg-emerald-600 hover:bg-emerald-600 text-white shadow-emerald-500/35'
				: ''}"
			aria-pressed={voteState === 'upvote'}
			aria-label="Upvote"
			disabled={disabled || busy}
			onpointerdown={() => handlePress('upvote')}
			onkeydown={(event) => {
				if (event.key === 'Enter' || event.key === ' ') handlePress('upvote');
			}}
			onclick={() => pick(voteState === 'upvote' ? 'neutral' : 'upvote')}
		>
			<ThumbsUpIcon
				class="size-4 {upBounce ? 'thumb-bounce' : ''}"
				onanimationend={() => (upBounce = false)}
			/>
		</Button>
		<span
			class="text-emerald-600 text-xs tabular-nums transition-transform duration-150 ease-out {voteState ===
			'upvote'
				? 'scale-110'
				: ''}"
			aria-label="Upvotes">+{upvotes}</span
		>
	</div>
	<div class="flex flex-col items-center gap-1">
		<Button
			type="button"
			variant={voteState === 'downvote' ? 'destructive' : 'outline'}
			size="icon-sm"
			class="vote-button size-8 rounded-full shadow-sm transition-all duration-150 ease-out {voteState ===
			'downvote'
				? 'shadow-red-500/35'
				: ''}"
			aria-pressed={voteState === 'downvote'}
			aria-label="Downvote"
			disabled={disabled || busy}
			onpointerdown={() => handlePress('downvote')}
			onkeydown={(event) => {
				if (event.key === 'Enter' || event.key === ' ') handlePress('downvote');
			}}
			onclick={() => pick(voteState === 'downvote' ? 'neutral' : 'downvote')}
		>
			<ThumbsDownIcon
				class="size-4 {downBounce ? 'thumb-bounce' : ''}"
				onanimationend={() => (downBounce = false)}
			/>
		</Button>
		<span
			class="text-red-600 text-xs tabular-nums transition-transform duration-150 ease-out {voteState ===
			'downvote'
				? 'scale-110'
				: ''}"
			aria-label="Downvotes">-{downvotes}</span
		>
	</div>
</div>

<style>
	:global(.thumb-bounce) {
		animation: thumb-bounce 240ms cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	:global(.vote-button:active svg) {
		transform: scale(0.95);
	}

	@keyframes thumb-bounce {
		0% {
			transform: scale(0.9) translateY(0);
		}
		38% {
			transform: scale(1.2) translateY(-2px);
		}
		70% {
			transform: scale(0.96) translateY(1px);
		}
		100% {
			transform: scale(1) translateY(0);
		}
	}
</style>
