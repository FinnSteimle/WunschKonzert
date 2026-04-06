<script lang="ts">
	import CopyIcon from '@lucide/svelte/icons/copy';
	import CheckIcon from '@lucide/svelte/icons/check';
	import { Button, type ButtonSize, type ButtonVariant } from '$lib/components/ui/button';
	import { cn } from '$lib/utils.js';
	import { toast } from 'svelte-sonner';
	import { onDestroy } from 'svelte';

	const COPIED_MS = 2000;

	let {
		textToCopy,
		label,
		variant = 'outline',
		size = 'default',
		class: className
	}: {
		textToCopy: string;
		label: string;
		variant?: ButtonVariant;
		size?: ButtonSize;
		class?: string;
	} = $props();

	let copied = $state(false);
	let timeoutId: ReturnType<typeof setTimeout> | undefined;

	onDestroy(() => {
		if (timeoutId !== undefined) clearTimeout(timeoutId);
	});

	async function handleClick() {
		try {
			await navigator.clipboard.writeText(textToCopy);
			copied = true;
			if (timeoutId !== undefined) clearTimeout(timeoutId);
			timeoutId = setTimeout(() => {
				copied = false;
				timeoutId = undefined;
			}, COPIED_MS);
		} catch {
			toast.error('Could not copy to clipboard');
		}
	}
</script>

<Button
	type="button"
	{variant}
	{size}
	class={cn('relative shrink-0 gap-2', className)}
	onclick={handleClick}
	aria-live="polite"
	aria-label={copied ? 'Copied to clipboard' : label}
>
	<span
		class="inline-grid grid-cols-1 grid-rows-1 place-items-center [&>*]:col-start-1 [&>*]:row-start-1"
		aria-hidden="true"
	>
		<span
			class="inline-flex items-center gap-2 whitespace-nowrap transition-opacity duration-200 ease-out"
			class:opacity-0={copied}
			class:pointer-events-none={copied}
		>
			<CopyIcon class="size-4 shrink-0" />
			{label}
		</span>
		<span
			class="inline-flex items-center gap-2 whitespace-nowrap text-emerald-600 transition-opacity duration-200 ease-out dark:text-emerald-400"
			class:opacity-0={!copied}
			class:pointer-events-none={!copied}
		>
			<CheckIcon class="size-4 shrink-0" />
			Copied
		</span>
	</span>
</Button>
