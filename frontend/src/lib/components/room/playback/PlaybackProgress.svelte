<script lang="ts">
	import { onDestroy } from 'svelte';
	import { Progress } from '$lib/components/ui/progress';

	let {
		positionMs,
		durationMs,
		playbackState
	}: {
		positionMs: number;
		durationMs: number;
		playbackState?: 'playing' | 'paused' | 'stopped' | undefined;
	} = $props();

	let tickOffset = $state(0);
	let intervalId: ReturnType<typeof setInterval> | null = null;

	function startTicking() {
		stopTicking();
		tickOffset = 0;
		intervalId = setInterval(() => {
			tickOffset += 1000;
		}, 1000);
	}

	function stopTicking() {
		if (intervalId !== null) {
			clearInterval(intervalId);
			intervalId = null;
		}
		tickOffset = 0;
	}

	// Reset tick offset whenever the server sends a new position.
	$effect(() => {
		void positionMs;
		tickOffset = 0;
	});

	$effect(() => {
		if (playbackState === 'playing' && durationMs > 0) {
			startTicking();
		} else {
			stopTicking();
		}
	});

	onDestroy(stopTicking);

	const displayMs = $derived(Math.min(positionMs + tickOffset, durationMs));

	function formatMs(ms: number): string {
		if (!Number.isFinite(ms) || ms < 0) return '0:00';
		const totalSec = Math.floor(ms / 1000);
		const m = Math.floor(totalSec / 60);
		const s = totalSec % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	const pct = $derived.by(() => {
		if (!durationMs || durationMs <= 0) return 0;
		return Math.min(100, Math.max(0, (displayMs / durationMs) * 100));
	});
</script>

<div class="flex w-full min-w-0 flex-col gap-2" aria-label="Playback progress">
	<Progress value={pct} max={100} class="h-1.5" />
	<div class="text-muted-foreground flex justify-between text-xs tabular-nums">
		<span>{formatMs(displayMs)}</span>
		{#if playbackState}
			<span class="capitalize">{playbackState}</span>
		{/if}
		<span>{formatMs(durationMs)}</span>
	</div>
</div>
