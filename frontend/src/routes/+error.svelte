<script lang="ts">
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import {
		Card,
		CardContent,
		CardDescription,
		CardFooter,
		CardHeader,
		CardTitle
	} from '$lib/components/ui/card';
</script>

<svelte:head>
	<title>Error {page.status}</title>
</svelte:head>

<div class="bg-background flex min-h-[100dvh] items-center justify-center px-4 py-12">
	<Card class="w-full max-w-md min-w-0 shadow-sm">
		<CardHeader>
			<CardTitle class="text-xl">Something went wrong</CardTitle>
			<CardDescription>HTTP {page.status}</CardDescription>
		</CardHeader>
		<CardContent>
			<p class="text-muted-foreground text-sm">
				{String(page.error?.message ?? 'An unexpected error occurred.')}
			</p>
		</CardContent>
		<CardFooter>
			<Button href="/" class="w-full sm:w-auto">Back home</Button>
		</CardFooter>
	</Card>
</div>
