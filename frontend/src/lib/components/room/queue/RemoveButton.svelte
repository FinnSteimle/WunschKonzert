<script lang="ts">
	import Trash2Icon from '@lucide/svelte/icons/trash-2';
	import SkipForwardIcon from '@lucide/svelte/icons/skip-forward';
	import { Button } from '$lib/components/ui/button';

	/**
	 * Three visual states:
	 *
	 * canRemoveDirectly = true  → "Remove" button (host or adder)
	 *                             Instantly removes the track, no vote needed.
	 *                             If others have voted, shows x/n counter as a warning.
	 *
	 * canRemoveDirectly = false, skipCount === 0
	 *                           → "Neutral" button (no vote started yet)
	 *                             Tapping casts a skip vote.
	 *
	 * canRemoveDirectly = false, skipCount > 0
	 *                           → "Voting" button (vote in progress)
	 *                             Shows x/n counter. Highlighted if current user voted.
	 *                             Tapping TOGGLES the vote:
	 *                               - not voted → casts skip vote
	 *                               - already voted → rescinds (sends neutral)
	 *                             Toggle logic lives in QueueItem, not here.
	 */
	let {
		canRemoveDirectly,
		skipCount,
		requiredVotes,
		hasVoted,
		busy = false,
		onRemove
	}: {
		canRemoveDirectly: boolean;
		skipCount: number;
		requiredVotes: number;
		hasVoted: boolean;
		busy?: boolean;
		onRemove?: () => void;
	} = $props();

	let bounce = $state(false);

	function handleClick() {
		if (busy) return;
		bounce = true;
		onRemove?.();
	}

	const mode = $derived(canRemoveDirectly ? 'remove' : skipCount > 0 ? 'voting' : 'neutral');
</script>

<div class="flex flex-col items-center gap-1">
	{#if mode === 'remove'}
		<Button
			type="button"
			variant="outline"
			size="icon-sm"
			class="remove-button size-8 rounded-full shadow-sm transition-all duration-150 ease-out
				hover:border-red-500 hover:bg-red-50 hover:text-red-600
				dark:hover:bg-red-950 dark:hover:text-red-400
				{skipCount > 0 ? 'border-orange-400 text-orange-500' : ''}"
			aria-label="Remove track{skipCount > 0
				? ` (${skipCount} of ${requiredVotes} votes to skip)`
				: ''}"
			disabled={busy}
			onclick={handleClick}
		>
			<Trash2Icon
				class="size-4 {bounce ? 'remove-bounce' : ''}"
				onanimationend={() => (bounce = false)}
			/>
		</Button>
		{#if skipCount > 0}
			<span
				class="tabular-nums text-[10px] text-orange-500 transition-transform duration-150 ease-out"
				aria-label="{skipCount} of {requiredVotes} votes to skip"
			>
				{skipCount}/{requiredVotes}
			</span>
		{:else}
			<span class="text-muted-foreground text-[10px]">Remove</span>
		{/if}
	{:else if mode === 'neutral'}
		<Button
			type="button"
			variant="outline"
			size="icon-sm"
			class="remove-button size-8 rounded-full shadow-sm transition-all duration-150 ease-out
				hover:border-orange-400 hover:bg-orange-50 hover:text-orange-600
				dark:hover:bg-orange-950 dark:hover:text-orange-400"
			aria-label="Vote to remove track"
			disabled={busy}
			onclick={handleClick}
		>
			<SkipForwardIcon
				class="size-4 {bounce ? 'remove-bounce' : ''}"
				onanimationend={() => (bounce = false)}
			/>
		</Button>
		<span class="text-muted-foreground text-[10px]">Skip</span>
	{:else}
		<Button
			type="button"
			variant={hasVoted ? 'default' : 'outline'}
			size="icon-sm"
			class="remove-button size-8 rounded-full shadow-sm transition-all duration-150 ease-out
				{hasVoted
				? 'bg-orange-500 hover:bg-orange-500 text-white shadow-orange-400/35'
				: 'hover:border-orange-400 hover:bg-orange-50 hover:text-orange-600 dark:hover:bg-orange-950 dark:hover:text-orange-400'}"
			aria-pressed={hasVoted}
			aria-label="Vote to remove track ({skipCount} of {requiredVotes})"
			disabled={busy}
			onclick={handleClick}
		>
			<SkipForwardIcon
				class="size-4 {bounce ? 'remove-bounce' : ''}"
				onanimationend={() => (bounce = false)}
			/>
		</Button>
		<span
			class="tabular-nums text-[10px] transition-transform duration-150 ease-out
				{hasVoted ? 'scale-110 text-orange-500' : 'text-muted-foreground'}"
			aria-label="{skipCount} of {requiredVotes} votes to remove"
		>
			{skipCount}/{requiredVotes}
		</span>
	{/if}
</div>

<style>
	:global(.remove-bounce) {
		animation: remove-bounce 240ms cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	:global(.remove-button:active svg) {
		transform: scale(0.95);
	}

	@keyframes remove-bounce {
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
