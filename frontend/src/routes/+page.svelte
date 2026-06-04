<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import RoomCodeJoinForm from '$lib/components/room/forms/RoomCodeJoinForm.svelte';
	import RecentRoomsPanel from '$lib/components/home/RecentRoomsPanel.svelte';
	import ListMusicIcon from '@lucide/svelte/icons/list-music';
	import PlusIcon from '@lucide/svelte/icons/plus';
	import RadioIcon from '@lucide/svelte/icons/radio';
	import Share2Icon from '@lucide/svelte/icons/share-2';
	import UsersIcon from '@lucide/svelte/icons/users';
	import VoteIcon from '@lucide/svelte/icons/vote';

	type FeaturePlatform = {
		name: 'Spotify' | 'Apple Music';
		badgeClass: string;
	};

	type Feature = {
		icon: typeof UsersIcon;
		title: string;
		body: string;
		platforms?: FeaturePlatform[];
	};

	const features: Feature[] = [
		{
			icon: UsersIcon,
			title: 'Shared listening rooms',
			body: 'Hosts create a room with a short join code; guests enter it and listen together.'
		},
		{
			icon: ListMusicIcon,
			title: 'Suggest songs',
			body: 'Search tracks and add them to the queue so everyone can hear their picks.',
			platforms: [
				{
					name: 'Spotify',
					badgeClass:
						'border-[#1db954]/25 bg-[#1db954]/10 text-[#1db954] dark:border-[#1db954]/35 dark:bg-[#1db954]/15'
				},
				{
					name: 'Apple Music',
					badgeClass:
						'border-[#fc3c44]/25 bg-[#fc3c44]/10 text-[#fc3c44] dark:border-[#fc3c44]/35 dark:bg-[#fc3c44]/15'
				}
			]
		},
		{
			icon: VoteIcon,
			title: 'Vote on the queue',
			body: 'Democratic playback: vote for what should play next and shape the set list.'
		},
		{
			icon: RadioIcon,
			title: 'Synced playback',
			body: 'Playback stays aligned in real time so the group experiences the same moment.'
		},
		{
			icon: Share2Icon,
			title: 'Easy invites',
			body: 'Share the code or link. Guests can join without creating an account.'
		},
		{
			icon: UsersIcon,
			title: 'Host controls',
			body: 'Room hosts steer the session and keep the queue organized during playback.'
		}
	];
</script>

<svelte:head>
	<title>WunschKonzert | Collaborative listening rooms</title>
	<meta
		name="description"
		content="WunschKonzert is a collaborative music room: join with a code, suggest songs from Spotify and Apple Music, vote on the queue, and listen in sync."
	/>
</svelte:head>

<div class="bg-background min-h-dvh">
	<div
		class="mx-auto flex w-full min-w-0 max-w-7xl flex-col gap-10 px-4 py-8 sm:gap-12 sm:px-6 sm:py-12 lg:gap-12 lg:px-8 xl:gap-14 xl:px-10"
	>
		<section
			class="border-border from-primary/8 via-background to-background relative w-full min-w-0 overflow-hidden rounded-2xl border bg-linear-to-b p-6 sm:p-8 lg:p-8 xl:p-10"
			aria-labelledby="wk-hero-heading"
		>
			<header
				class="flex w-full flex-col gap-6 text-center sm:text-left lg:flex-row lg:items-center lg:justify-between lg:gap-10 xl:gap-16"
			>
				<div
					class="flex flex-col items-center gap-3 sm:flex-row sm:items-start lg:min-w-0 lg:flex-1"
				>
					<img
						src="/logo.svg"
						alt=""
						class="ring-border h-12 w-12 shrink-0 rounded-xl ring-1 sm:h-14 sm:w-14"
					/>
					<div class="min-w-0 space-y-2">
						<p class="text-primary text-xs font-medium uppercase tracking-wider">
							Collaborative listening
						</p>
						<h1
							id="wk-hero-heading"
							class="text-3xl font-semibold tracking-tight sm:text-4xl xl:text-5xl"
						>
							WunschKonzert
						</h1>
					</div>
				</div>
				<p
					class="text-muted-foreground w-full max-w-none text-center text-base leading-relaxed sm:text-left sm:text-lg lg:min-w-0 lg:flex-1 xl:text-lg"
				>
					A real-time group music room: suggest songs, vote on what plays next, and stay in sync.
					Built for parties, offices, and anyone who wants a shared queue.
				</p>
			</header>
		</section>

		<div
			class="flex min-w-0 flex-col gap-10 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(18rem,26rem)] lg:items-start lg:gap-10 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,28rem)] xl:gap-14"
		>
			<div
				class="grid min-w-0 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-2 xl:grid-cols-2 xl:gap-4"
				aria-label="Features"
			>
				{#each features as item (item.title)}
					<div
						class="border-border bg-card/80 flex gap-3 rounded-xl border p-4 shadow-sm backdrop-blur-sm"
					>
						<div
							class="bg-primary/10 text-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
						>
							<item.icon class="h-5 w-5" aria-hidden="true" />
						</div>
						<div class="min-w-0 space-y-1">
							<h2 class="text-sm font-semibold leading-snug">{item.title}</h2>
							<p class="text-muted-foreground text-xs leading-relaxed">{item.body}</p>
							{#if item.platforms}
								<div class="mt-2 flex flex-wrap gap-2" aria-label="Supported music services">
									{#each item.platforms as platform (platform.name)}
										<span
											class={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-medium leading-none ${platform.badgeClass}`}
										>
											{#if platform.name === 'Spotify'}
												<svg
													viewBox="0 0 24 24"
													class="h-3.5 w-3.5"
													fill="currentColor"
													aria-hidden="true"
												>
													<path
														d="M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0Zm5.5 17.3a.75.75 0 0 1-1.03.24c-2.82-1.72-6.36-2.11-10.51-1.18a.75.75 0 1 1-.33-1.46c4.54-1.02 8.48-.58 11.62 1.34.35.21.46.67.25 1.02Zm1.48-3.28a.94.94 0 0 1-1.29.31c-3.23-1.99-8.14-2.57-11.96-1.42a.94.94 0 0 1-.54-1.8c4.37-1.31 9.79-.67 13.48 1.6.44.27.58.85.31 1.3Zm.13-3.43c-3.87-2.3-10.26-2.51-13.95-1.38a1.13 1.13 0 0 1-.66-2.16c4.24-1.29 11.29-1.04 15.76 1.6a1.13 1.13 0 0 1-1.15 1.94Z"
													/>
												</svg>
											{:else if platform.name === 'Apple Music'}
												<svg
													viewBox="0 0 24 24"
													class="h-3.5 w-3.5"
													fill="currentColor"
													aria-hidden="true"
												>
													<path
														d="M15.7 4.1a3.2 3.2 0 0 0-2.3 1.1 3 3 0 0 0-.8 2.2c.9.1 1.7-.3 2.3-.9.6-.6 1-1.5.8-2.4ZM18.8 12.7c0-2.1 1.7-3.2 1.8-3.3-1-1.5-2.6-1.7-3.1-1.7-1.3-.1-2.5.8-3.2.8-.6 0-1.7-.8-2.8-.8-1.5 0-2.8.8-3.6 2-.7 1.2-1 2.6-1 3.9 0 3.1 2 6.3 4.1 6.3 1 0 1.7-.7 3-.7 1.2 0 1.8.7 3 .7 2.2 0 3.6-2 4.2-3.2a3.5 3.5 0 0 1-2.4-3.3Z"
													/>
												</svg>
											{/if}
											{platform.name}
										</span>
									{/each}
								</div>
							{/if}
						</div>
					</div>
				{/each}
			</div>

			<div class="flex min-w-0 flex-col gap-8 lg:sticky lg:top-8 lg:self-start lg:pb-2">
				<RecentRoomsPanel />

				<Card class="min-w-0 shadow-sm">
					<CardHeader>
						<CardTitle>Join with code</CardTitle>
						<CardDescription>Enter the 6-character code from the host.</CardDescription>
					</CardHeader>
					<CardContent>
						<RoomCodeJoinForm />
					</CardContent>
				</Card>

				<div
					class="flex flex-col items-center gap-3 sm:flex-row sm:justify-between lg:flex-col lg:items-stretch xl:flex-row xl:items-center xl:justify-between"
				>
					<p
						class="text-muted-foreground text-center text-sm sm:text-left lg:text-center xl:text-left"
					>
						Hosting a session?
					</p>
					<Button href="/create" class="w-full sm:w-auto lg:w-full xl:w-auto">
						<PlusIcon class="h-4 w-4" aria-hidden="true" />
						Create a room
					</Button>
				</div>
			</div>
		</div>
	</div>
</div>
