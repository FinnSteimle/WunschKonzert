<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { ModeWatcher } from 'mode-watcher';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import { Toaster } from '$lib/components/ui/sonner';

	let { children } = $props();
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<ModeWatcher />
<Toaster position="top-center" richColors closeButton />
<div class="pointer-events-none fixed top-4 right-4 z-50">
	<div class="pointer-events-auto">
		<ThemeToggle />
	</div>
</div>
{@render children()}
