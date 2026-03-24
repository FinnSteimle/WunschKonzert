<script lang="ts">
	import PauseIcon from '@lucide/svelte/icons/pause';
	import PlayIcon from '@lucide/svelte/icons/play';
	import SquareIcon from '@lucide/svelte/icons/square';
	import { Button } from '$lib/components/ui/button';

	let {
		disabled = false,
		playbackState,
		busy = false,
		onPlaybackAction
	}: {
		disabled?: boolean;
		playbackState?: 'playing' | 'paused' | 'stopped';
		busy?: boolean;
		onPlaybackAction?: (action: 'pause' | 'resume' | 'stop') => void;
	} = $props();

	const isPlaying = $derived(playbackState === 'playing');
</script>

<div class="flex flex-wrap items-center gap-2">
	<Button
		type="button"
		variant="secondary"
		size="sm"
		class="gap-2"
		disabled={disabled || busy}
		onclick={() => onPlaybackAction?.(isPlaying ? 'pause' : 'resume')}
	>
		{#if isPlaying}
			<PauseIcon class="size-4" aria-hidden="true" />
			Pause
		{:else}
			<PlayIcon class="size-4" aria-hidden="true" />
			Resume
		{/if}
	</Button>
	<Button
		type="button"
		variant="outline"
		size="sm"
		class="gap-2"
		disabled={disabled || busy || playbackState === 'stopped'}
		onclick={() => onPlaybackAction?.('stop')}
	>
		<SquareIcon class="size-4" aria-hidden="true" />
		Stop
	</Button>
</div>
