<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import type { RoomStateDto } from '$lib/types/api';
	import EmptyState from '$lib/components/room/states/EmptyState.svelte';

	let {
		users,
		hostUserId,
		currentUserId,
		onEditSelf
	}: {
		users: RoomStateDto['users'];
		hostUserId: string;
		currentUserId: string;
		onEditSelf?: () => void;
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
			<EmptyState
				title="No listeners yet"
				description="Share the invite link to gather the crowd."
			/>
		{:else}
			<ul class="flex flex-col gap-2" aria-label="Room members">
				{#each active as row (row.user.userId)}
					{@const isSelf = row.user.userId === currentUserId}
					<li
						class="flex min-w-0 items-center justify-between gap-2 rounded-md border px-3 py-2 {isSelf
							? 'border-primary/30 bg-primary/10 ring-1 ring-primary/15 dark:bg-primary/15'
							: 'border-border'}"
						aria-current={isSelf ? 'true' : undefined}
					>
						<div class="flex min-w-0 items-center gap-1">
							<span class="truncate text-sm font-medium">{row.user.displayName}</span>
							{#if isSelf}
								<Button
									type="button"
									variant="ghost"
									size="icon"
									class="size-7 shrink-0"
									onclick={() => onEditSelf?.()}
									aria-label="Edit display name"
								>
									<PencilIcon class="size-4" />
								</Button>
							{/if}
						</div>
						<div class="flex shrink-0 flex-wrap items-center justify-end gap-1">
							{#if isSelf}
								<Badge variant="default" class="text-[10px] font-semibold">You</Badge>
							{/if}
							{#if row.user.userId === hostUserId}
								<Badge variant="secondary" class="text-[10px]">Host</Badge>
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	</CardContent>
</Card>
