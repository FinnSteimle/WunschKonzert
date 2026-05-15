import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CreatePage from './+page.svelte';
import { apiClient } from '$lib/api/client';
import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';
import { recordRecentRoom } from '$lib/session/recentRooms';
import { toast } from 'svelte-sonner';
import { goto } from '$app/navigation';
import { resolve } from '$app/paths';

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: vi.fn((path: string, params?: { roomId?: string }) =>
		path === '/room/[roomId]' && params?.roomId ? `/room/${params.roomId}` : path
	)
}));

vi.mock('$app/state', () => ({
	page: {
		url: new URL('http://localhost/create?spotify_linked=true')
	}
}));

vi.mock('$lib/api/client', () => ({
	apiClient: {
		createRoom: vi.fn()
	}
}));

vi.mock('$lib/session/userSession', () => ({
	getOrCreateSessionUser: vi.fn(),
	saveSessionDisplayName: vi.fn(),
	generateRandomDisplayName: vi.fn(() => 'DJ Fox')
}));

vi.mock('$lib/session/recentRooms', () => ({
	recordRecentRoom: vi.fn()
}));

vi.mock('svelte-sonner', () => ({
	toast: {
		error: vi.fn(),
		success: vi.fn()
	}
}));

function deferred<T>() {
	let resolvePromise!: (value: T) => void;
	let rejectPromise!: (error?: unknown) => void;
	const promise = new Promise<T>((res, rej) => {
		resolvePromise = res;
		rejectPromise = rej;
	});
	return { promise, resolvePromise, rejectPromise };
}

describe('create room route', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.clearAllMocks();
		vi.mocked(getOrCreateSessionUser).mockReturnValue({
			userId: 'U_ROUTE1234',
			displayName: 'Alice'
		});
	});

	it('navigates to room with join code after successful create', async () => {
		vi.mocked(apiClient.createRoom).mockResolvedValue({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'ZX9WV8'
		});

		render(CreatePage);

		await fireEvent.input(screen.getByLabelText('Room name'), {
			target: { value: 'Friday vibes' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		await waitFor(() => expect(goto).toHaveBeenCalledWith('/room/ZX9WV8'));
		expect(resolve).toHaveBeenCalledWith('/room/[roomId]', { roomId: 'ZX9WV8' });
		expect(saveSessionDisplayName).toHaveBeenCalledWith('Alice');
		expect(recordRecentRoom).toHaveBeenCalledWith({
			joinCode: 'ZX9WV8',
			name: 'Friday vibes',
			isHost: true
		});
	});

	it('shows api error and does not navigate when create fails', async () => {
		vi.mocked(apiClient.createRoom).mockResolvedValue({
			success: false,
			message: 'Could not create',
			room_id: null,
			join_code: null
		});

		render(CreatePage);

		await fireEvent.input(screen.getByLabelText('Room name'), {
			target: { value: 'Friday vibes' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Could not create'));
		expect(goto).not.toHaveBeenCalled();
	});

	it('prevents duplicate submits while request is pending', async () => {
		const request = deferred<{
			success: boolean;
			message: string;
			room_id: string;
			join_code: string;
		}>();
		vi.mocked(apiClient.createRoom).mockReturnValue(request.promise);

		render(CreatePage);

		await fireEvent.input(screen.getByLabelText('Room name'), {
			target: { value: 'Friday vibes' }
		});
		const submitButton = screen.getByRole('button', { name: 'Create room' });
		await fireEvent.click(submitButton);
		await fireEvent.click(screen.getByRole('button', { name: 'Creating…' }));

		expect(apiClient.createRoom).toHaveBeenCalledTimes(1);

		request.resolvePromise({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'ZX9WV8'
		});

		await waitFor(() => expect(goto).toHaveBeenCalledWith('/room/ZX9WV8'));
	});
});
