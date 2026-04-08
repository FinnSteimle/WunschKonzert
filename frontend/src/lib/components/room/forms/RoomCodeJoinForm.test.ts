import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RoomCodeJoinForm from './RoomCodeJoinForm.svelte';
import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';
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

vi.mock('$lib/session/userSession', () => ({
	getOrCreateSessionUser: vi.fn(),
	saveSessionDisplayName: vi.fn(),
	generateRandomDisplayName: vi.fn(() => 'DJ Fox')
}));

vi.mock('svelte-sonner', () => ({
	toast: {
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

describe('RoomCodeJoinForm', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.clearAllMocks();
		vi.mocked(getOrCreateSessionUser).mockReturnValue({
			userId: 'U_JOIN12345',
			displayName: 'Alice'
		});
		vi.mocked(goto).mockResolvedValue();
	});

	it('prefills display name from session user on mount', () => {
		render(RoomCodeJoinForm);

		expect((screen.getByLabelText('Your display name') as HTMLInputElement).value).toBe('Alice');
	});

	it('shows an error for invalid room code and does not navigate', async () => {
		render(RoomCodeJoinForm);

		await fireEvent.input(screen.getByLabelText('Room code'), { target: { value: 'abc12' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect(toast.error).toHaveBeenCalledWith('Enter a valid 6-character room code.');
		expect(goto).not.toHaveBeenCalled();
	});

	it('shows an error when display name is empty', async () => {
		vi.mocked(getOrCreateSessionUser).mockReturnValue({
			userId: 'U_JOIN12345',
			displayName: ''
		});
		render(RoomCodeJoinForm);

		await fireEvent.input(screen.getByLabelText('Room code'), { target: { value: 'ab2cd3' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect(toast.error).toHaveBeenCalledWith('Please enter your display name.');
		expect(goto).not.toHaveBeenCalled();
	});

	it('normalizes code and navigates to room route on submit', async () => {
		render(RoomCodeJoinForm);

		await fireEvent.input(screen.getByLabelText('Room code'), { target: { value: ' ab 2cd3 ' } });
		await fireEvent.input(screen.getByLabelText('Your display name'), {
			target: { value: '  Alice Cooper  ' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		await waitFor(() => expect(resolve).toHaveBeenCalledWith('/room/[roomId]', { roomId: 'AB2CD3' }));
		expect(goto).toHaveBeenCalledWith('/room/AB2CD3');
		expect(saveSessionDisplayName).toHaveBeenCalledWith('Alice Cooper');
		// Called on mount for prefill and again on submit.
		expect(getOrCreateSessionUser).toHaveBeenCalledTimes(2);
	});

	it('shows busy state while navigation is in flight', async () => {
		const navigation = deferred<void>();
		vi.mocked(goto).mockReturnValue(navigation.promise);
		render(RoomCodeJoinForm);

		await fireEvent.input(screen.getByLabelText('Room code'), { target: { value: 'ab2cd3' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect((screen.getByRole('button', { name: 'Joining…' }) as HTMLButtonElement).disabled).toBe(true);
		expect((screen.getByLabelText('Room code') as HTMLInputElement).disabled).toBe(true);
		expect((screen.getByLabelText('Your display name') as HTMLInputElement).disabled).toBe(true);

		navigation.resolvePromise();

		await waitFor(() =>
			expect((screen.getByRole('button', { name: 'Join room' }) as HTMLButtonElement).disabled).toBe(
				false
			)
		);
	});
});
