<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		title,
		description,
		children
	}: {
		title: string;
		description?: string;
		children?: Snippet;
	} = $props();
</script>

<div
	class="border-border bg-muted/30 flex min-h-48 min-w-0 flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-10 text-center"
	role="status"
>
	<p class="text-foreground text-base font-medium">{title}</p>
	{#if description}
		<p class="text-muted-foreground max-w-sm text-sm">{description}</p>
	{/if}
	{#if children}
		<div class="mt-2 flex flex-wrap items-center justify-center gap-2">{@render children()}</div>
	{/if}
</div>
