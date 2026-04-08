import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LeaveRoomButton from './LeaveRoomButton.svelte';
import { apiClient } from '$lib/api/client';
import { toast } from 'svelte-sonner';
import { goto } from '$app/navigation';
import { resolve } from '$app/paths';

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: vi.fn((path: string) => path)
}));

vi.mock('$lib/api/client', () => ({
	apiClient: {
		leaveRoom: vi.fn()
	}
}));

vi.mock('svelte-sonner', () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn()
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

describe('LeaveRoomButton', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('leaves room and navigates home on success', async () => {
		const request = deferred<{
			success: boolean;
			message: string;
			room_id: string | null;
			join_code: string | null;
		}>();
		vi.mocked(apiClient.leaveRoom).mockReturnValue(request.promise);

		render(LeaveRoomButton, {
			roomId: 'room-1',
			userId: 'user-1'
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Leave room' }));

		expect(apiClient.leaveRoom).toHaveBeenCalledWith({ room_id: 'room-1', user_id: 'user-1' });
		expect(screen.getByRole('button', { name: 'Leaving…' })).toBeTruthy();

		request.resolvePromise({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'AB12CD'
		});

		await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Left room'));
		expect(resolve).toHaveBeenCalledWith('/');
		expect(goto).toHaveBeenCalledWith('/');
		expect(screen.getByRole('button', { name: 'Leave room' })).toBeTruthy();
	});

	it('shows error when leaving room fails', async () => {
		vi.mocked(apiClient.leaveRoom).mockRejectedValue(new Error('Request failed'));

		render(LeaveRoomButton, {
			roomId: 'room-1',
			userId: 'user-1'
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Leave room' }));

		await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Request failed'));
		expect(goto).not.toHaveBeenCalled();
		expect(screen.getByRole('button', { name: 'Leave room' })).toBeTruthy();
	});

	it('is disabled when disabled prop is true', () => {
		render(LeaveRoomButton, {
			roomId: 'room-1',
			userId: 'user-1',
			disabled: true
		});

		expect((screen.getByRole('button', { name: 'Leave room' }) as HTMLButtonElement).disabled).toBe(
			true
		);
	});
});
