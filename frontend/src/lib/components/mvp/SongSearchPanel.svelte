<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Button } from '$lib/components/ui/button';
	import { apiClient } from '$lib/api/client';
	import type { TrackDto } from '$lib/types/api';
	import SearchResultList from './SearchResultList.svelte';
	import LoadingState from './LoadingState.svelte';
	import EmptyState from './EmptyState.svelte';
	import { toast } from 'svelte-sonner';

	let {
		roomId,
		onTrackAdded,
		onAddTrack
	}: {
		roomId: string;
		onTrackAdded?: (track: TrackDto) => void;
		onAddTrack?: (track: TrackDto) => Promise<void> | void;
	} = $props();

	let query = $state('');
	let results = $state<TrackDto[]>([]);
	let searchBusy = $state(false);
	let searchError = $state<string | null>(null);
	let addingTrackId = $state<string | null>(null);

	let debounceTimer: ReturnType<typeof setTimeout> | null = null;

	onDestroy(() => {
		if (debounceTimer) clearTimeout(debounceTimer);
	});

	function scheduleSearch(q: string) {
		if (debounceTimer) clearTimeout(debounceTimer);
		const trimmed = q.trim();
		if (trimmed.length < 2) {
			results = [];
			searchError = null;
			return;
		}
		debounceTimer = setTimeout(() => {
			void runSearch(trimmed);
		}, 320);
	}

	function onQueryInput() {
		if (browser) scheduleSearch(query);
	}

	async function runSearch(q: string) {
		searchBusy = true;
		searchError = null;
		try {
			const res = await apiClient.searchSongs(roomId, q);
			results = res.tracks ?? [];
		} catch (err) {
			searchError = err instanceof Error ? err.message : 'Search failed';
			results = [];
		} finally {
			searchBusy = false;
		}
	}

	async function addTrack(track: TrackDto) {
		addingTrackId = track.trackId;
		try {
			if (!onAddTrack) {
				throw new Error('Add action unavailable');
			}
			await onAddTrack(track);
			toast.success('Added to queue');
			onTrackAdded?.(track);
		} catch (err) {
			toast.error(err instanceof Error ? err.message : 'Could not add song');
		} finally {
			addingTrackId = null;
		}
	}
</script>

<div class="flex w-full min-w-0 flex-col gap-3">
	<div class="flex flex-col gap-2">
		<Label for="wk-search">Search songs</Label>
		<div class="flex flex-col gap-2 min-[400px]:flex-row">
			<Input
				id="wk-search"
				type="search"
				placeholder="Artist or track name"
				bind:value={query}
				autocomplete="off"
				class="min-w-0 flex-1"
				oninput={onQueryInput}
			/>
			<Button
				type="button"
				variant="secondary"
				class="w-full shrink-0 min-[400px]:w-auto"
				disabled={searchBusy || query.trim().length < 2}
				onclick={() => void runSearch(query.trim())}
			>
				Search
			</Button>
		</div>
		<p class="text-muted-foreground text-xs">Type at least two characters. Results update as you type.</p>
	</div>

	{#if searchBusy && results.length === 0}
		<LoadingState message="Searching…" />
	{:else if searchError}
		<EmptyState title="Search failed" description={searchError} />
	{:else}
		<SearchResultList tracks={results} {addingTrackId} onAdd={addTrack} />
	{/if}
</div>
