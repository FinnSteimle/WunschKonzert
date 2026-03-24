<script lang="ts">
	import CopyIcon from '@lucide/svelte/icons/copy';
	import {
		Card,
		CardContent,
		CardDescription,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Badge } from '$lib/components/ui/badge';
	import QRCodeCard from './QRCodeCard.svelte';
	import { toast } from 'svelte-sonner';

	let {
		joinCode,
		inviteUrl
	}: {
		joinCode: string;
		inviteUrl: string;
	} = $props();

	async function copy(text: string, label: string) {
		try {
			await navigator.clipboard.writeText(text);
			toast.success(`Copied ${label}`);
		} catch {
			toast.error('Could not copy to clipboard');
		}
	}
</script>

<div class="flex w-full min-w-0 flex-col gap-4">
	<Card class="min-w-0">
		<CardHeader class="pb-2">
			<CardTitle class="text-base">Room code</CardTitle>
			<CardDescription>Share this code so others can join manually.</CardDescription>
		</CardHeader>
		<CardContent class="flex flex-col gap-3 sm:flex-row sm:items-center">
			<Badge variant="secondary" class="font-mono text-lg tracking-widest">{joinCode}</Badge>
			<Button
				type="button"
				variant="outline"
				size="sm"
				class="shrink-0 gap-2"
				onclick={() => copy(joinCode, 'room code')}
			>
				<CopyIcon class="size-4" aria-hidden="true" />
				Copy code
			</Button>
		</CardContent>
	</Card>

	<Card class="min-w-0">
		<CardHeader class="pb-2">
			<CardTitle class="text-base">Invite link</CardTitle>
			<CardDescription>Send this link — guests join in one tap.</CardDescription>
		</CardHeader>
		<CardContent class="flex flex-col gap-2">
			<div class="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-stretch">
				<Input class="min-w-0 font-mono text-xs sm:text-sm" readonly value={inviteUrl} />
				<Button
					type="button"
					variant="outline"
					class="shrink-0 gap-2 sm:w-auto"
					onclick={() => copy(inviteUrl, 'invite link')}
				>
					<CopyIcon class="size-4" aria-hidden="true" />
					Copy link
				</Button>
			</div>
		</CardContent>
	</Card>

	<QRCodeCard {inviteUrl} />
</div>
