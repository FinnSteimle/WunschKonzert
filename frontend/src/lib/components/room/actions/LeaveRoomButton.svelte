<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { Button } from '$lib/components/ui/button';
	import { apiClient } from '$lib/api/client';
	import { toast } from 'svelte-sonner';

	let {
		roomId,
		userId,
		disabled = false
	}: {
		roomId: string;
		userId: string;
		disabled?: boolean;
	} = $props();

	let busy = $state(false);

	async function leave() {
		if (busy) return;
		busy = true;
		try {
			await apiClient.leaveRoom({ room_id: roomId, user_id: userId });
			toast.success('Left room');
			await goto(resolve('/'));
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not leave room');
		} finally {
			busy = false;
		}
	}
</script>

<Button
	type="button"
	variant="outline"
	class="w-full min-[400px]:w-auto"
	disabled={disabled || busy}
	onclick={leave}
>
	{busy ? 'Leaving…' : 'Leave room'}
</Button>
