import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RoomCodeJoinForm from './RoomCodeJoinForm.svelte';
import {
	generateRandomDisplayName,
	getOrCreateSessionUser,
	saveSessionDisplayName
} from '$lib/session/userSession';
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

function getCodeInputs() {
	return Array.from({ length: 6 }, (_, index) =>
		screen.getByLabelText(`Room code character ${index + 1}`)
	) as HTMLInputElement[];
}

async function typeRoomCode(rawCode: string) {
	const codeInputs = getCodeInputs();
	const normalized = rawCode.replace(/\s/g, '').toUpperCase().slice(0, 6);
	for (const [index, char] of normalized.split('').entries()) {
		await fireEvent.input(codeInputs[index], { target: { value: char } });
	}
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

	it('auto-generates and persists a display name when no name is stored yet', () => {
		vi.mocked(getOrCreateSessionUser).mockReturnValue({
			userId: 'U_JOIN12345',
			displayName: ''
		});
		vi.mocked(generateRandomDisplayName).mockReturnValue('DJ Fox');

		render(RoomCodeJoinForm);

		expect((screen.getByLabelText('Your display name') as HTMLInputElement).value).toBe('DJ Fox');
		expect(saveSessionDisplayName).toHaveBeenCalledWith('DJ Fox');
	});

	it('shows an error for invalid room code and does not navigate', async () => {
		render(RoomCodeJoinForm);

		await typeRoomCode('abc12');
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect(toast.error).toHaveBeenCalledWith('Enter a valid 6-character room code.');
		expect(goto).not.toHaveBeenCalled();
	});

	it('rejects disallowed room-code characters I, O, 0, and 1', async () => {
		render(RoomCodeJoinForm);

		for (const code of ['AB1CD3', 'AB0CD3', 'ABICD3', 'ABOCD3']) {
			await typeRoomCode(code);
			await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));
		}

		expect(goto).not.toHaveBeenCalled();
		expect(toast.error).toHaveBeenCalledTimes(4);
		expect(toast.error).toHaveBeenNthCalledWith(1, 'Enter a valid 6-character room code.');
	});

	it('rejects whitespace-only room codes', async () => {
		render(RoomCodeJoinForm);

		await typeRoomCode('      ');
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect(toast.error).toHaveBeenCalledWith('Enter a valid 6-character room code.');
		expect(goto).not.toHaveBeenCalled();
	});

	it('shows an error when display name is empty', async () => {
		render(RoomCodeJoinForm);

		await typeRoomCode('ab2cd3');
		await fireEvent.input(screen.getByLabelText('Your display name'), { target: { value: '' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect(toast.error).toHaveBeenCalledWith('Please enter your display name.');
		expect(goto).not.toHaveBeenCalled();
	});

	it('rejects whitespace-only display names', async () => {
		render(RoomCodeJoinForm);

		await typeRoomCode('AB2CD3');
		await fireEvent.input(screen.getByLabelText('Your display name'), { target: { value: '    ' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect(toast.error).toHaveBeenCalledWith('Please enter your display name.');
		expect(goto).not.toHaveBeenCalled();
	});

	it('normalizes code and navigates to room route on submit', async () => {
		render(RoomCodeJoinForm);

		await typeRoomCode(' ab 2cd3 ');
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

	it('normalizes pasted room codes in the multi-field input', async () => {
		render(RoomCodeJoinForm);
		const codeInputs = getCodeInputs();
		await fireEvent.paste(codeInputs[0], {
			clipboardData: { getData: () => '  ab 2cd3  ' }
		});

		expect(codeInputs.map((input) => input.value).join('')).toBe('AB2CD3');
	});

	it('always pastes room code from the first field', async () => {
		render(RoomCodeJoinForm);
		const codeInputs = getCodeInputs();
		await fireEvent.paste(codeInputs[3], {
			clipboardData: { getData: () => 'CD2EF3' }
		});

		expect(codeInputs.map((input) => input.value).join('')).toBe('CD2EF3');
	});

	it('shows busy state while navigation is in flight', async () => {
		const navigation = deferred<void>();
		vi.mocked(goto).mockReturnValue(navigation.promise);
		render(RoomCodeJoinForm);

		await typeRoomCode('ab2cd3');
		await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

		expect((screen.getByRole('button', { name: 'Joining…' }) as HTMLButtonElement).disabled).toBe(true);
		for (const input of getCodeInputs()) {
			expect(input.disabled).toBe(true);
		}
		expect((screen.getByLabelText('Your display name') as HTMLInputElement).disabled).toBe(true);

		navigation.resolvePromise();

		await waitFor(() =>
			expect((screen.getByRole('button', { name: 'Join room' }) as HTMLButtonElement).disabled).toBe(
				false
			)
		);
	});
});
