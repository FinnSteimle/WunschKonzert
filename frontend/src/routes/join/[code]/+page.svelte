<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { apiClient } from '$lib/api/client';
	import { getOrCreateSessionUser } from '$lib/session/userSession';
	import LoadingState from '$lib/components/mvp/LoadingState.svelte';
	import EmptyState from '$lib/components/mvp/EmptyState.svelte';
	import { Button } from '$lib/components/ui/button';

	let status = $state<'idle' | 'joining' | 'error'>('idle');
	let message = $state<string | null>(null);

	onMount(() => {
		const raw = page.params.code ?? '';
		const code = raw.replace(/\s/g, '').toUpperCase();
		if (!/^[A-HJ-NP-Z2-9]{6}$/.test(code)) {
			status = 'error';
			message = 'This invite link does not contain a valid room code.';
			return;
		}

		status = 'joining';
		const { userId } = getOrCreateSessionUser();
		void (async () => {
			try {
				const res = await apiClient.joinRoom({ room_id: code, user_id: userId });
				if (!res.success || !res.room_id) {
					throw new Error(res.message || 'Could not join this room.');
				}
				await goto(`/room/${res.room_id}`);
			} catch (err) {
				status = 'error';
				message = err instanceof Error ? err.message : 'Could not join this room.';
			}
		})();
	});
</script>

<svelte:head>
	<title>Joining room…</title>
</svelte:head>

<div class="bg-background min-h-dvh">
	<div class="mx-auto w-full max-w-md min-w-0 px-4 py-12">
		{#if status === 'joining'}
			<LoadingState message="Joining room…" />
		{:else if status === 'error'}
			<EmptyState title="Could not join" description={message ?? 'Something went wrong.'}>
				<Button href="/">Back home</Button>
			</EmptyState>
		{/if}
	</div>
</div>
