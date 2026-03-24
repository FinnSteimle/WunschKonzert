<script lang="ts">
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { apiClient } from '$lib/api/client';
	import { getOrCreateSessionUser } from '$lib/session/userSession';
	import { toast } from 'svelte-sonner';

	let code = $state('');
	let busy = $state(false);

	const JOIN_ALPHABET_RE = /^[A-HJ-NP-Z2-9]{6}$/i;

	function normalize(raw: string): string {
		return raw.replace(/\s/g, '').toUpperCase().slice(0, 6);
	}

	async function submit(e: Event) {
		e.preventDefault();
		const normalized = normalize(code);
		if (!JOIN_ALPHABET_RE.test(normalized)) {
			toast.error('Enter a valid 6-character room code.');
			return;
		}
		busy = true;
		try {
			const { userId } = getOrCreateSessionUser();
			const res = await apiClient.joinRoom({ room_id: normalized, user_id: userId });
			if (!res.success || !res.room_id) {
				throw new Error(res.message || 'Could not join room');
			}
			toast.success('Joined room');
			await goto(`/room/${res.room_id}`);
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not join room');
		} finally {
			busy = false;
		}
	}
</script>

<form class="flex w-full min-w-0 flex-col gap-4" onsubmit={submit}>
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
		<p class="text-muted-foreground text-xs">Six characters, letters and numbers (no I, O, 0, 1).</p>
	</div>
	<Button type="submit" class="w-full min-[400px]:w-auto" disabled={busy}>
		{busy ? 'Joining…' : 'Join room'}
	</Button>
</form>
