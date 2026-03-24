<script lang="ts">
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button';
	import {
		AlertDialog,
		AlertDialogCancel,
		AlertDialogContent,
		AlertDialogDescription,
		AlertDialogFooter,
		AlertDialogHeader,
		AlertDialogTitle
	} from '$lib/components/ui/alert-dialog';
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

	let open = $state(false);
	let busy = $state(false);

	async function confirmDelete() {
		busy = true;
		try {
			await apiClient.deleteRoom({ room_id: roomId, user_id: userId });
			toast.success('Room deleted');
			open = false;
			await goto('/');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not delete room');
		} finally {
			busy = false;
		}
	}
</script>

<Button
	type="button"
	variant="destructive"
	class="w-full min-[400px]:w-auto"
	disabled={disabled || busy}
	onclick={() => (open = true)}
>
	Delete room
</Button>

<AlertDialog bind:open>
	<AlertDialogContent>
		<AlertDialogHeader>
			<AlertDialogTitle>Delete this room?</AlertDialogTitle>
			<AlertDialogDescription>
				This stops playback and removes the room for everyone. This cannot be undone.
			</AlertDialogDescription>
		</AlertDialogHeader>
		<AlertDialogFooter class="gap-2 sm:space-x-0">
			<AlertDialogCancel type="button" disabled={busy}>Cancel</AlertDialogCancel>
			<Button
				type="button"
				variant="destructive"
				disabled={busy}
				onclick={() => void confirmDelete()}
			>
				{busy ? 'Deleting…' : 'Delete forever'}
			</Button>
		</AlertDialogFooter>
	</AlertDialogContent>
</AlertDialog>
