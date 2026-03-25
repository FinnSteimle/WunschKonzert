<script lang="ts">
	import { onMount } from 'svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import {
		NativeSelect,
		NativeSelectOption
	} from '$lib/components/ui/native-select';
	import { apiClient } from '$lib/api/client';
	import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';
	import { recordRecentRoom } from '$lib/session/recentRooms';
	import type { ProviderId } from '$lib/types/api';
	import { toast } from 'svelte-sonner';

	let {
		onsuccess
	}: {
		onsuccess?: (payload: { roomId: string; joinCode: string }) => void;
	} = $props();

	let name = $state('');
	let displayName = $state('');
	let provider = $state<ProviderId>('spotify');
	let busy = $state(false);

	onMount(() => {
		displayName = getOrCreateSessionUser().displayName;
	});

	async function submit(e: Event) {
		e.preventDefault();
		const trimmed = name.trim();
		const trimmedDisplay = displayName.trim();
		if (!trimmed) {
			toast.error('Please enter a room name.');
			return;
		}
		if (!trimmedDisplay) {
			toast.error('Please enter your display name.');
			return;
		}
		busy = true;
		try {
			saveSessionDisplayName(trimmedDisplay);
			const { userId } = getOrCreateSessionUser();
			const res = await apiClient.createRoom({
				name: trimmed,
				user_id: userId,
				display_name: trimmedDisplay,
				supported_provider_id: provider
			});
			if (!res.success || !res.room_id || !res.join_code) {
				throw new Error(res.message || 'Could not create room');
			}
			toast.success('Room created');
			recordRecentRoom({
				joinCode: res.join_code,
				name: trimmed,
				isHost: true
			});
			onsuccess?.({ roomId: res.room_id, joinCode: res.join_code });
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not create room');
		} finally {
			busy = false;
		}
	}
</script>

<form class="flex w-full min-w-0 flex-col gap-4" onsubmit={submit}>
	<div class="flex flex-col gap-2">
		<Label for="wk-display-name-create">Your display name</Label>
		<Input
			id="wk-display-name-create"
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
		<Label for="wk-room-name">Room name</Label>
		<Input
			id="wk-room-name"
			name="name"
			type="text"
			placeholder="Friday vibes"
			bind:value={name}
			disabled={busy}
			maxlength={120}
		/>
	</div>
	<div class="flex w-full min-w-0 flex-col gap-2">
		<Label for="wk-provider">Music provider</Label>
		<NativeSelect id="wk-provider" bind:value={provider} class="w-full" disabled={busy}>
			<NativeSelectOption value="spotify">Spotify</NativeSelectOption>
		</NativeSelect>
	</div>
	<Button type="submit" class="w-full min-[400px]:w-auto" disabled={busy}>
		{busy ? 'Creating…' : 'Create room'}
	</Button>
</form>
