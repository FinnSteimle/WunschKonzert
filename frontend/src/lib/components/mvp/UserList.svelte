<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import type { RoomStateDto } from '$lib/types/api';
	import EmptyState from './EmptyState.svelte';

	let {
		users,
		hostUserId
	}: {
		users: RoomStateDto['users'];
		hostUserId: string;
	} = $props();

	const active = $derived(users.filter((u) => u.membership.leftAt == null));
</script>

<Card class="min-w-0">
	<CardHeader class="pb-2">
		<CardTitle class="text-base">People here</CardTitle>
		<CardDescription>Everyone currently in the room.</CardDescription>
	</CardHeader>
	<CardContent class="pt-0">
		{#if active.length === 0}
			<EmptyState title="No listeners yet" description="Share the invite link to gather the crowd." />
		{:else}
			<ul class="flex flex-col gap-2" aria-label="Room members">
				{#each active as row (row.user.userId)}
					<li
						class="border-border flex min-w-0 items-center justify-between gap-2 rounded-md border px-3 py-2"
					>
						<span class="truncate text-sm font-medium">{row.user.displayName}</span>
						{#if row.user.userId === hostUserId}
							<Badge variant="secondary" class="shrink-0 text-[10px]">Host</Badge>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</CardContent>
</Card>
