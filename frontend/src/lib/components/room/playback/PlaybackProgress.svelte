<script lang="ts">
	import { Progress } from '$lib/components/ui/progress';

	let {
		positionMs,
		durationMs,
		state
	}: {
		positionMs: number;
		durationMs: number;
		state?: 'playing' | 'paused' | 'stopped' | undefined;
	} = $props();

	function formatMs(ms: number): string {
		if (!Number.isFinite(ms) || ms < 0) return '0:00';
		const totalSec = Math.floor(ms / 1000);
		const m = Math.floor(totalSec / 60);
		const s = totalSec % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	const pct = $derived.by(() => {
		if (!durationMs || durationMs <= 0) return 0;
		return Math.min(100, Math.max(0, (positionMs / durationMs) * 100));
	});
</script>

<div class="flex w-full min-w-0 flex-col gap-2" aria-label="Playback progress">
	<Progress value={pct} max={100} class="h-1.5" />
	<div class="text-muted-foreground flex justify-between text-xs tabular-nums">
		<span>{formatMs(positionMs)}</span>
		{#if state}
			<span class="capitalize">{state}</span>
		{/if}
		<span>{formatMs(durationMs)}</span>
	</div>
</div>
