<script lang="ts">
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Button } from '$lib/components/ui/button';
	import DicesIcon from '@lucide/svelte/icons/dices';
	import { generateRandomDisplayName } from '$lib/session/userSession';

	let {
		id,
		value = $bindable(''),
		disabled = false,
		maxlength = 120
	}: {
		id: string;
		value: string;
		disabled?: boolean;
		maxlength?: number;
	} = $props();

	const SCRAMBLE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz';

	let spinning = $state(false);
	let displayChars = $state<string[]>([]);
	let lockedCount = $state(0);

	function randomChar(): string {
		return SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
	}

	async function randomize() {
		if (spinning || disabled) return;
		spinning = true;

		const target = generateRandomDisplayName();
		const len = target.length;
		lockedCount = 0;
		displayChars = Array.from({ length: len }, () => randomChar());

		const SCRAMBLE_INTERVAL = 32;
		const LOCK_DELAY = 20;

		let cancelled = false;

		const scrambleHandle = setInterval(() => {
			displayChars = displayChars.map((ch, i) => (i < lockedCount ? target[i] : randomChar()));
		}, SCRAMBLE_INTERVAL);

		for (let i = 0; i < len; i++) {
			await new Promise((r) => setTimeout(r, LOCK_DELAY));
			if (cancelled) break;
			lockedCount = i + 1;
			displayChars[i] = target[i];
		}

		clearInterval(scrambleHandle);
		cancelled = true;
		displayChars = [...target];
		value = target;
		spinning = false;
	}
</script>

<div class="flex flex-col gap-2">
	<Label for={id}>Your display name</Label>
	<div class="flex gap-2">
		<div class="relative min-w-0 flex-1">
			{#if spinning}
				<div
					class="slot-overlay border-input bg-background flex h-9 w-full items-center overflow-hidden rounded-md border px-3 py-1 text-base shadow-xs md:text-sm"
					aria-hidden="true"
				>
					{#each displayChars as ch, i (i)}
						<span
							class="slot-char inline-block"
							class:locked={i < lockedCount}
							class:tumbling={i >= lockedCount}
						>
							{ch}
						</span>
					{/each}
				</div>
			{/if}
			<Input
				{id}
				name="displayName"
				type="text"
				placeholder="How others see you"
				bind:value
				{disabled}
				{maxlength}
				autocomplete="nickname"
				class={spinning ? 'invisible' : ''}
			/>
		</div>
		<Button
			type="button"
			variant="outline"
			size="icon"
			disabled={disabled || spinning}
			onclick={randomize}
			aria-label="Randomize display name"
			class="shrink-0"
		>
			<DicesIcon class={['size-4', spinning && 'dice-spin']} />
		</Button>
	</div>
</div>

<style>
	.slot-overlay {
		position: absolute;
		inset: 0;
		z-index: 1;
		pointer-events: none;
	}

	.slot-char {
		position: relative;
		display: inline-block;
		text-align: center;
		will-change: transform, opacity;
	}

	.slot-char.tumbling {
		animation: tumble 0.12s steps(1) infinite;
		color: hsl(var(--muted-foreground));
	}

	.slot-char.locked {
		animation: lock-pop 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
		color: hsl(var(--foreground));
	}

	@keyframes tumble {
		0% {
			transform: translateY(-40%);
			opacity: 0.4;
		}
		25% {
			transform: translateY(0);
			opacity: 1;
		}
		50% {
			transform: translateY(40%);
			opacity: 0.4;
		}
		75% {
			transform: translateY(0);
			opacity: 1;
		}
	}

	@keyframes lock-pop {
		0% {
			transform: scale(1.4) translateY(-20%);
			opacity: 0.6;
		}
		60% {
			transform: scale(1.1) translateY(0);
			opacity: 1;
		}
		100% {
			transform: scale(1) translateY(0);
			opacity: 1;
		}
	}

	:global(.dice-spin) {
		animation: dice-roll 0.6s cubic-bezier(0.4, 0, 0.2, 1) infinite;
	}

	@keyframes dice-roll {
		0% {
			transform: rotate(0deg);
		}
		100% {
			transform: rotate(360deg);
		}
	}
</style>
