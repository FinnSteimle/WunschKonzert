<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import LogInIcon from '@lucide/svelte/icons/log-in';
	import { Button } from '$lib/components/ui/button';
	import { Label } from '$lib/components/ui/label';
	import DisplayNameInput from '$lib/components/room/forms/DisplayNameInput.svelte';
	import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';
	import { toast } from 'svelte-sonner';

	let codeChars = $state<string[]>(Array(6).fill(''));
	let code = $derived(codeChars.join(''));
	let displayName = $state('');
	let busy = $state(false);

	onMount(() => {
		displayName = getOrCreateSessionUser().displayName;
	});

	const JOIN_ALPHABET_RE = /^[A-HJ-NP-Z2-9]{6}$/i;
	const JOIN_CHAR_RE = /^[A-HJ-NP-Z2-9]$/i;

	function normalize(raw: string): string {
		return raw.replace(/\s/g, '').toUpperCase().slice(0, 6);
	}

	let codeInputs = $state<(HTMLInputElement | null)[]>(Array(6).fill(null));

	function focusInput(index: number) {
		const target = codeInputs[index];
		if (!target || busy) return;
		target.focus();
		target.select();
	}

	function setCodeAt(index: number, char: string) {
		const next = [...codeChars];
		next[index] = char;
		codeChars = next;
	}

	function applyChunk(startIndex: number, raw: string) {
		const chunk = normalize(raw);
		if (!chunk) return;

		const next = [...codeChars];
		let writeIndex = startIndex;
		for (const char of chunk) {
			if (writeIndex > 5) break;
			next[writeIndex] = char;
			writeIndex += 1;
		}
		codeChars = next;
		focusInput(Math.min(writeIndex, 5));
	}

	function handleCharInput(index: number, event: Event) {
		const target = event.currentTarget as HTMLInputElement;
		const raw = target.value.toUpperCase();
		if (!raw) {
			setCodeAt(index, '');
			return;
		}

		if (raw.length > 1) {
			applyChunk(index, raw);
			return;
		}

		if (!JOIN_CHAR_RE.test(raw)) {
			target.value = codeChars[index].trim();
			return;
		}

		setCodeAt(index, raw);
		if (index < 5) focusInput(index + 1);
	}

	function handleKeydown(index: number, event: KeyboardEvent) {
		const currentChar = codeChars[index].trim();
		if (event.key === 'Backspace' && !currentChar && index > 0) {
			event.preventDefault();
			setCodeAt(index - 1, '');
			focusInput(index - 1);
			return;
		}

		if (event.key === 'ArrowLeft' && index > 0) {
			event.preventDefault();
			focusInput(index - 1);
			return;
		}

		if (event.key === 'ArrowRight' && index < 5) {
			event.preventDefault();
			focusInput(index + 1);
		}
	}

	function handlePaste(_index: number, event: ClipboardEvent) {
		const pasted = event.clipboardData?.getData('text') ?? '';
		if (!pasted) return;
		event.preventDefault();
		applyChunk(0, pasted);
	}

	async function submit(e: Event) {
		e.preventDefault();
		const normalized = normalize(code);
		const trimmedDisplay = displayName.trim();
		if (!JOIN_ALPHABET_RE.test(normalized)) {
			toast.error('Enter a valid 6-character room code.');
			return;
		}
		if (!trimmedDisplay) {
			toast.error('Please enter your display name.');
			return;
		}
		saveSessionDisplayName(trimmedDisplay);
		getOrCreateSessionUser();
		busy = true;
		try {
			await goto(resolve('/room/[roomId]', { roomId: normalized }));
		} finally {
			busy = false;
		}
	}
</script>

<form class="flex w-full min-w-0 flex-col gap-4" onsubmit={submit}>
	<DisplayNameInput id="wk-display-name-join" bind:value={displayName} disabled={busy} />
	<div class="flex flex-col gap-2">
		<Label for="wk-join-code-0">Room code</Label>
		<div class="grid grid-cols-6 gap-2" aria-label="Room code input">
			{#each codeChars as char, index (index)}
				<input
					id={`wk-join-code-${index}`}
					bind:this={codeInputs[index]}
					type="text"
					inputmode="text"
					autocomplete="one-time-code"
					autocapitalize="characters"
					maxlength={1}
					class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex h-10 w-full rounded-md border text-center font-mono text-lg uppercase shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
					value={char.trim()}
					oninput={(event) => handleCharInput(index, event)}
					onkeydown={(event) => handleKeydown(index, event)}
					onpaste={(event) => handlePaste(index, event)}
					disabled={busy}
					aria-label={`Room code character ${index + 1}`}
					aria-invalid={code.length > 0 && !JOIN_ALPHABET_RE.test(normalize(code))}
				/>
			{/each}
		</div>
		<p class="text-muted-foreground text-xs">Six characters, letters and numbers.</p>
	</div>
	<Button type="submit" class="w-full min-[400px]:w-auto" disabled={busy}>
		<LogInIcon class="h-4 w-4" aria-hidden="true" />
		{busy ? 'Joining…' : 'Join room'}
	</Button>
</form>
