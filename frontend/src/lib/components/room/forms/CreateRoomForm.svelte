<script lang="ts">
	import { onMount } from 'svelte';
	import CheckIcon from '@lucide/svelte/icons/check';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { NativeSelect, NativeSelectOption } from '$lib/components/ui/native-select';
	import DisplayNameInput from '$lib/components/room/forms/DisplayNameInput.svelte';
	import { apiClient } from '$lib/api/client';
	import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';
	import { recordRecentRoom } from '$lib/session/recentRooms';
	import type { ProviderId } from '$lib/types/api';
	import { toast } from 'svelte-sonner';

	let {
		onsuccess,
		spotifyLinked = false
	}: {
		onsuccess?: (payload: { roomId: string; joinCode: string }) => void;
		spotifyLinked?: boolean;
	} = $props();

	let name = $state('');
	let displayName = $state('');
	let provider = $state<ProviderId>('spotify');
	let busy = $state(false);
	let linkBusy = $state(false);

	const providerLinked = $derived(provider === 'spotify' && spotifyLinked);
	const canCreate = $derived(providerLinked);
	const MAX_ROOM_NAME_LENGTH = 40;
	const SUPPORTED_PROVIDERS: ProviderId[] = ['spotify'];

	onMount(() => {
		displayName = getOrCreateSessionUser().displayName;
	});

	async function linkSpotify() {
		const trimmedDisplay = displayName.trim();
		if (!trimmedDisplay) {
			toast.error('Please enter your display name first.');
			return;
		}
		linkBusy = true;
		try {
			saveSessionDisplayName(trimmedDisplay);
			const { userId } = getOrCreateSessionUser();
			const returnTo = window.location.origin + '/create';
			const { auth_url } = await apiClient.getSpotifyLoginUrl(userId, returnTo);
			window.location.href = auth_url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not start Spotify login');
			linkBusy = false;
		}
	}

	async function submit(e: Event) {
		e.preventDefault();
		const trimmed = name.trim();
		const trimmedDisplay = displayName.trim();
		if (!trimmed) {
			toast.error('Please enter a room name.');
			return;
		}
		if (trimmed.length > MAX_ROOM_NAME_LENGTH) {
			toast.error(`Room name must be ${MAX_ROOM_NAME_LENGTH} characters or fewer.`);
			return;
		}
		if (!trimmedDisplay) {
			toast.error('Please enter your display name.');
			return;
		}
		if (!canCreate) {
			toast.error('Please link your Spotify account first.');
			return;
		}
		if (!SUPPORTED_PROVIDERS.includes(provider)) {
			toast.error('Please choose a supported music provider.');
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
	<DisplayNameInput id="wk-display-name-create" bind:value={displayName} disabled={busy} />
	<div class="flex flex-col gap-2">
		<Label for="wk-room-name">Room name</Label>
		<Input
			id="wk-room-name"
			name="name"
			type="text"
			placeholder="Friday vibes"
			bind:value={name}
			disabled={busy}
			maxlength={MAX_ROOM_NAME_LENGTH}
		/>
	</div>
	<div class="flex w-full min-w-0 flex-col gap-2">
		<Label for="wk-provider">Music provider</Label>
		<NativeSelect id="wk-provider" bind:value={provider} class="w-full" disabled={busy}>
			<NativeSelectOption value="spotify">Spotify</NativeSelectOption>
		</NativeSelect>
	</div>

	{#if provider === 'spotify'}
		<div class="flex flex-col gap-2">
			{#if spotifyLinked}
				<div class="text-sm flex items-center gap-1.5 text-green-600 dark:text-green-400">
					<CheckIcon class="size-4" aria-hidden="true" />
					Spotify account linked
				</div>
			{:else}
				<Button
					type="button"
					variant="outline"
					class="w-full min-[400px]:w-auto"
					disabled={linkBusy}
					onclick={linkSpotify}
				>
					{linkBusy ? 'Redirecting…' : 'Link Spotify account'}
				</Button>
				<p class="text-muted-foreground text-xs">
					A Spotify Premium account is required to play music in the room.
				</p>
			{/if}
		</div>
	{/if}

	<Button type="submit" class="w-full min-[400px]:w-auto" disabled={busy || !canCreate}>
		{busy ? 'Creating…' : 'Create room'}
	</Button>
</form>
