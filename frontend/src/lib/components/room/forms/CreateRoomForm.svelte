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
	import { linkAppleMusicAccount } from '$lib/providers/appleMusicAuth';
	import { PROVIDER_LABELS, SUPPORTED_PROVIDERS } from '$lib/providers/constants';
	import { getAppleMusicLinkStatus, isProviderLinkedForUser } from '$lib/providers/linkStatus';
	import type { ProviderId } from '$lib/types/api';
	import { toast } from 'svelte-sonner';

	let {
		onsuccess,
		spotifyLinked = false
	}: {
		onsuccess?: (payload: { roomId: string; joinCode: string }) => void;
		/** Set after Spotify OAuth redirect (`?spotify_linked=true`). */
		spotifyLinked?: boolean;
	} = $props();

	let name = $state('');
	let displayName = $state('');
	let provider = $state<ProviderId>('spotify');
	let busy = $state(false);
	let linkBusy = $state(false);
	let linkStatus = $state<Record<ProviderId, boolean>>({
		spotify: false,
		'apple-music': false
	});
	let appleNeedsRelink = $state(false);

	const providerLinked = $derived(linkStatus[provider] === true);
	const canCreate = $derived(providerLinked);
	const MAX_ROOM_NAME_LENGTH = 40;

	onMount(() => {
		displayName = getOrCreateSessionUser().displayName;
		const savedName = sessionStorage.getItem('wk_pending_room_name');
		if (savedName) {
			name = savedName;
			sessionStorage.removeItem('wk_pending_room_name');
		}
		void refreshLinkStatus();
	});

	async function refreshLinkStatus(): Promise<void> {
		const { userId } = getOrCreateSessionUser();
		linkStatus.spotify = spotifyLinked || (await isProviderLinkedForUser('spotify', userId));
		const appleStatus = await getAppleMusicLinkStatus(userId);
		appleNeedsRelink = appleStatus.needsRelink;
		linkStatus['apple-music'] = appleStatus.linked;
	}

	async function linkSpotify() {
		const trimmedDisplay = displayName.trim();
		if (!trimmedDisplay) {
			toast.error('Please enter your display name first.');
			return;
		}
		linkBusy = true;
		try {
			saveSessionDisplayName(trimmedDisplay);
			if (name.trim()) {
				sessionStorage.setItem('wk_pending_room_name', name.trim());
			}
			const { userId } = getOrCreateSessionUser();
			const returnTo = window.location.origin + '/create';
			const { auth_url } = await apiClient.getSpotifyLoginUrl(userId, returnTo);
			window.location.href = auth_url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not start Spotify login');
			linkBusy = false;
		}
	}

	async function linkAppleMusic() {
		const trimmedDisplay = displayName.trim();
		if (!trimmedDisplay) {
			toast.error('Please enter your display name first.');
			return;
		}
		linkBusy = true;
		try {
			saveSessionDisplayName(trimmedDisplay);
			if (name.trim()) {
				sessionStorage.setItem('wk_pending_room_name', name.trim());
			}
			const { userId } = getOrCreateSessionUser();
			await linkAppleMusicAccount(userId, trimmedDisplay);
			await refreshLinkStatus();
			toast.success('Apple Music account linked');
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not link Apple Music');
		} finally {
			linkBusy = false;
		}
	}

	async function submit(e: Event) {
		e.preventDefault();
		if (busy || linkBusy) {
			return;
		}
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
			toast.error(`Please link your ${PROVIDER_LABELS[provider]} account first.`);
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
			{#each SUPPORTED_PROVIDERS as providerId (providerId)}
				<NativeSelectOption value={providerId}>{PROVIDER_LABELS[providerId]}</NativeSelectOption>
			{/each}
		</NativeSelect>
	</div>

	{#if provider === 'spotify'}
		<div class="flex flex-col gap-2">
			{#if linkStatus.spotify}
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
	{:else if provider === 'apple-music'}
		<div class="flex flex-col gap-2">
			{#if linkStatus['apple-music']}
				<div class="text-sm flex items-center gap-1.5 text-green-600 dark:text-green-400">
					<CheckIcon class="size-4" aria-hidden="true" />
					Apple Music account linked
				</div>
			{:else}
				<Button
					type="button"
					variant="outline"
					class="w-full min-[400px]:w-auto"
					disabled={linkBusy}
					onclick={linkAppleMusic}
				>
					{linkBusy
						? 'Connecting…'
						: appleNeedsRelink
							? 'Re-link Apple Music account'
							: 'Link Apple Music account'}
				</Button>
				<p class="text-muted-foreground text-xs">
					An active Apple Music subscription is required to play music in the room.
				</p>
			{/if}
		</div>
	{/if}

	<Button type="submit" class="w-full min-[400px]:w-auto" disabled={busy || !canCreate}>
		{busy ? 'Creating…' : 'Create room'}
	</Button>
</form>
