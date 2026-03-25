<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';
	import { toast } from 'svelte-sonner';

	let code = $state('');
	let displayName = $state('');
	let busy = $state(false);

	onMount(() => {
		displayName = getOrCreateSessionUser().displayName;
	});

	const JOIN_ALPHABET_RE = /^[A-HJ-NP-Z2-9]{6}$/i;

	function normalize(raw: string): string {
		return raw.replace(/\s/g, '').toUpperCase().slice(0, 6);
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
		if (browser) {
			sessionStorage.setItem('wk_prefilled_join_code', normalized);
		}
		busy = true;
		try {
			await goto(resolve('/room/[roomId]', { roomId: normalized }));
		} finally {
			busy = false;
		}
	}
</script>

<form class="flex w-full min-w-0 flex-col gap-4" onsubmit={submit}>
	<div class="flex flex-col gap-2">
		<Label for="wk-display-name-join">Your display name</Label>
		<Input
			id="wk-display-name-join"
			name="displayName"
			type="text"
			placeholder="How others see you"
			bind:value={displayName}
			disabled={busy}
			maxlength={120}
			autocomplete="nickname"
		/>
	</div>
	<div class="flex flex-col gap-2">
		<Label for="wk-join-code">Room code</Label>
		<Input
			id="wk-join-code"
			name="code"
			type="text"
			inputmode="text"
			autocomplete="off"
			autocapitalize="characters"
			maxlength={6}
			placeholder="ABC123"
			class="font-mono text-lg tracking-widest uppercase"
			bind:value={code}
			oninput={() => (code = normalize(code))}
			disabled={busy}
			aria-invalid={code.length > 0 && !JOIN_ALPHABET_RE.test(normalize(code))}
		/>
		<p class="text-muted-foreground text-xs">
			Six characters, letters and numbers (no I, O, 0, 1).
		</p>
	</div>
	<Button type="submit" class="w-full min-[400px]:w-auto" disabled={busy}>
		{busy ? 'Joining…' : 'Join room'}
	</Button>
</form>
