<script lang="ts">
	import BellIcon from '@lucide/svelte/icons/bell';
	import CircleMinusIcon from '@lucide/svelte/icons/circle-minus';
	import CirclePlusIcon from '@lucide/svelte/icons/circle-plus';
	import CrownIcon from '@lucide/svelte/icons/crown';
	import InfoIcon from '@lucide/svelte/icons/info';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import RotateCcwIcon from '@lucide/svelte/icons/rotate-ccw';
	import ShieldAlertIcon from '@lucide/svelte/icons/shield-alert';
	import SkipForwardIcon from '@lucide/svelte/icons/skip-forward';
	import SquareIcon from '@lucide/svelte/icons/square';
	import StepForwardIcon from '@lucide/svelte/icons/step-forward';
	import ThumbsDownIcon from '@lucide/svelte/icons/thumbs-down';
	import ThumbsUpIcon from '@lucide/svelte/icons/thumbs-up';
	import UserMinusIcon from '@lucide/svelte/icons/user-minus';
	import { buttonVariants } from '$lib/components/ui/button';
	import * as Popover from '$lib/components/ui/popover';
	import type { LastActivityDto, RoomStateDto } from '$lib/types/api';
	import { cn } from '$lib/utils.js';

	let {
		activities,
		roomState,
		onMarkRead
	}: {
		activities: LastActivityDto[];
		roomState: RoomStateDto;
		onMarkRead?: () => void;
	} = $props();

	let open = $state(false);
	let openedSinceLastClose = false;
	const unreadCountLabel = $derived(activities.length >= 100 ? '99+' : String(activities.length));

	$effect(() => {
		if (open) {
			openedSinceLastClose = true;
			return;
		}
		if (!openedSinceLastClose) return;
		openedSinceLastClose = false;
		onMarkRead?.();
	});

	type ActivityTone = 'default' | 'positive' | 'warning' | 'important' | 'destructive';
	type ActivityIcon =
		| 'add'
		| 'remove'
		| 'up'
		| 'down'
		| 'skip'
		| 'replay'
		| 'stop'
		| 'advance'
		| 'leave'
		| 'rename'
		| 'host'
		| 'hostReject'
		| 'info';

	const activityMeta: Record<
		string,
		{
			icon: ActivityIcon;
			tone: ActivityTone;
			label: (activity: LastActivityDto, trackTitle: string | null) => string;
		}
	> = {
		track_added: {
			icon: 'add',
			tone: 'positive',
			label: (activity, trackTitle) => `${activity.username} added ${trackTitle ?? 'a track'}`
		},
		track_removed: {
			icon: 'remove',
			tone: 'warning',
			label: (activity, trackTitle) => `${activity.username} removed ${trackTitle ?? 'a track'}`
		},
		up_vote: {
			icon: 'up',
			tone: 'positive',
			label: (activity, trackTitle) => `${activity.username} upvoted ${trackTitle ?? 'a track'}`
		},
		down_vote: {
			icon: 'down',
			tone: 'warning',
			label: (activity, trackTitle) => `${activity.username} downvoted ${trackTitle ?? 'a track'}`
		},
		skip_vote: {
			icon: 'skip',
			tone: 'warning',
			label: (activity, trackTitle) => `${activity.username} voted to skip ${trackTitle ?? 'a track'}`
		},
		replay_vote: {
			icon: 'replay',
			tone: 'positive',
			label: (activity, trackTitle) => `${activity.username} voted to replay ${trackTitle ?? 'a track'}`
		},
		vote_cleared: {
			icon: 'info',
			tone: 'default',
			label: (activity, trackTitle) => `${activity.username} cleared a vote on ${trackTitle ?? 'a track'}`
		},
		playback_stopped: {
			icon: 'stop',
			tone: 'warning',
			label: (activity) => `${activity.username} stopped playback`
		},
		playback_advanced: {
			icon: 'advance',
			tone: 'positive',
			label: (activity) => `${activity.username} skipped to the next track`
		},
		user_left: {
			icon: 'leave',
			tone: 'default',
			label: (activity) => `${activity.username} left the room`
		},
		user_renamed: {
			icon: 'rename',
			tone: 'default',
			label: (activity) => `${activity.username} changed their display name`
		},
		host_transfer_initiated: {
			icon: 'host',
			tone: 'important',
			label: (activity) => `${activity.username} offered to transfer host`
		},
		host_transfer_rejected: {
			icon: 'hostReject',
			tone: 'warning',
			label: (activity) => `${activity.username} declined host transfer`
		},
		host_transfer_completed: {
			icon: 'host',
			tone: 'important',
			label: (activity) => `${activity.username} became the host`
		}
	};

	function metaFor(activity: LastActivityDto) {
		return (
			activityMeta[activity.type] ?? {
				icon: 'info' as const,
				tone: 'default' as const,
				label: (item: LastActivityDto) => `${item.username} did ${humanizeType(item.type)}`
			}
		);
	}

	function humanizeType(type: string): string {
		return type.replaceAll('_', ' ');
	}

	function trackTitleFor(activity: LastActivityDto): string | null {
		if (!activity.queueEntryId) return null;
		const entry = roomState.queue.find((item) => item.queueEntryId === activity.queueEntryId);
		if (!entry) return null;
		return `"${entry.track.title}"`;
	}

	function timeAgo(isoString: string): string {
		const date = new Date(isoString);
		if (Number.isNaN(date.getTime())) return '';
		const diffMs = Date.now() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);
		if (diffMins < 1) return 'just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
		return date.toLocaleDateString();
	}

	function itemClass(tone: ActivityTone): string {
		if (tone === 'important') {
			return 'border-violet-500/40 bg-violet-500/10 text-violet-950 dark:text-violet-100';
		}
		if (tone === 'positive') {
			return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-950 dark:text-emerald-100';
		}
		if (tone === 'warning') {
			return 'border-amber-500/35 bg-amber-500/10 text-amber-950 dark:text-amber-100';
		}
		if (tone === 'destructive') {
			return 'border-destructive/40 bg-destructive/10 text-destructive';
		}
		return 'border-border bg-muted/35';
	}

	function iconClass(tone: ActivityTone): string {
		if (tone === 'important') return 'bg-violet-500/15 text-violet-700 dark:text-violet-200';
		if (tone === 'positive') return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-200';
		if (tone === 'warning') return 'bg-amber-500/15 text-amber-700 dark:text-amber-200';
		if (tone === 'destructive') return 'bg-destructive/15 text-destructive';
		return 'bg-background text-muted-foreground';
	}
</script>

<Popover.Root bind:open>
	<Popover.Trigger
		type="button"
		class={cn(
			buttonVariants({ variant: activities.length > 0 ? 'default' : 'outline', size: 'default' }),
			'relative shrink-0 touch-manipulation gap-2'
		)}
		aria-label={`Unread room activity: ${unreadCountLabel}`}
	>
		<BellIcon class="size-4" aria-hidden="true" />
		<span class="hidden min-[430px]:inline">Activity</span>
		{#if activities.length > 0}
			<span
				class="bg-background text-foreground flex min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-semibold"
			>
				{unreadCountLabel}
			</span>
		{/if}
	</Popover.Trigger>
	<Popover.Content
		align="end"
		sideOffset={8}
		class="w-[calc(100vw-2rem)] max-w-sm p-3"
	>
		<div class="mb-3">
			<h2 class="text-base font-semibold">Unread activity</h2>
			<p class="text-muted-foreground text-sm">New room events since you last opened this popup.</p>
		</div>
		{#if activities.length === 0}
			<p class="text-muted-foreground rounded-md border border-dashed px-3 py-3 text-sm">
				No unread activity.
			</p>
		{:else}
			<ul
				class="flex max-h-[min(24rem,calc(100dvh-12rem))] flex-col gap-2 overflow-y-auto pr-1"
				aria-label="Unread room activity"
				aria-live="polite"
			>
				{#each activities as activity (`${activity.type}:${activity.userId}:${activity.queueEntryId ?? ''}:${activity.at}`)}
					{@const meta = metaFor(activity)}
					{@const icon = meta.icon}
					{@const trackTitle = trackTitleFor(activity)}
					<li class={`flex min-w-0 gap-2 rounded-lg border px-3 py-2 text-sm ${itemClass(meta.tone)}`}>
						<span
							class={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full ${iconClass(
								meta.tone
							)}`}
							aria-hidden="true"
						>
							{#if icon === 'add'}
								<CirclePlusIcon class="size-4" />
							{:else if icon === 'remove'}
								<CircleMinusIcon class="size-4" />
							{:else if icon === 'up'}
								<ThumbsUpIcon class="size-4" />
							{:else if icon === 'down'}
								<ThumbsDownIcon class="size-4" />
							{:else if icon === 'skip'}
								<SkipForwardIcon class="size-4" />
							{:else if icon === 'replay'}
								<RotateCcwIcon class="size-4" />
							{:else if icon === 'stop'}
								<SquareIcon class="size-4" />
							{:else if icon === 'advance'}
								<StepForwardIcon class="size-4" />
							{:else if icon === 'leave'}
								<UserMinusIcon class="size-4" />
							{:else if icon === 'rename'}
								<PencilIcon class="size-4" />
							{:else if icon === 'host'}
								<CrownIcon class="size-4" />
							{:else if icon === 'hostReject'}
								<ShieldAlertIcon class="size-4" />
							{:else}
								<InfoIcon class="size-4" />
							{/if}
						</span>
						<span class="min-w-0 flex-1">
							<span class="line-clamp-2 font-medium">{meta.label(activity, trackTitle)}</span>
							<span class="text-muted-foreground mt-0.5 block text-xs">{timeAgo(activity.at)}</span>
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</Popover.Content>
</Popover.Root>
