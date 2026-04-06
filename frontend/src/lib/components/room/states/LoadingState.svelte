<script lang="ts">
	import Loader2Icon from '@lucide/svelte/icons/loader-2';

	let { message = 'Loading…' }: { message?: string } = $props();
</script>

<div
	class="text-muted-foreground flex min-h-32 flex-col items-center justify-center gap-3 py-8 text-sm"
	role="status"
	aria-live="polite"
>
	<Loader2Icon class="size-8 animate-spin opacity-70" aria-hidden="true" />
	<span>{message}</span>
</div>
