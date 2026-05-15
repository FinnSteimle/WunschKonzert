<script lang="ts">
	import type { SystemMessageDto } from '$lib/types/api';

	let { messages }: { messages: SystemMessageDto[] } = $props();
</script>

{#if messages.length > 0}
	<ul class="flex flex-col gap-2" aria-label="Room notifications">
		{#each messages as message (message.id)}
			<li
				class="text-muted-foreground rounded-md border border-border bg-muted/40 px-3 py-2 text-sm"
			>
				{message.text}
			</li>
		{/each}
	</ul>
{/if}
