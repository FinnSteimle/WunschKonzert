import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CreateRoomForm from './CreateRoomForm.svelte';
import { apiClient } from '$lib/api/client';
import {
	generateRandomDisplayName,
	getOrCreateSessionUser,
	saveSessionDisplayName
} from '$lib/session/userSession';
import { recordRecentRoom } from '$lib/session/recentRooms';
import { toast } from 'svelte-sonner';

vi.mock('$lib/api/client', () => ({
	apiClient: {
		createRoom: vi.fn()
	}
}));

vi.mock('$lib/providers/linkStatus', () => ({
	isProviderLinkedForUser: vi.fn(async (providerId: string) => providerId === 'spotify'),
	getAppleMusicLinkStatus: vi.fn(async () => ({ linked: false, needsRelink: false }))
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
	let resolve!: (value: T) => void;
	let reject!: (error?: unknown) => void;
	const promise = new Promise<T>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

describe('CreateRoomForm', () => {
	beforeEach(() => {
		localStorage.clear();
		vi.clearAllMocks();
		vi.mocked(generateRandomDisplayName).mockReturnValue('DJ Fox');
		vi.mocked(getOrCreateSessionUser).mockReturnValue({
			userId: 'U_TESTUSER1',
			displayName: 'Alice'
		});
	});

	it('shows an error when room name is empty', async () => {
		render(CreateRoomForm, { spotifyLinked: true });

		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		expect(toast.error).toHaveBeenCalledWith('Please enter a room name.');
		expect(apiClient.createRoom).not.toHaveBeenCalled();
	});

	it('shows an error when display name is empty', async () => {
		vi.mocked(getOrCreateSessionUser).mockReturnValue({
			userId: 'U_TESTUSER1',
			displayName: ''
		});

		render(CreateRoomForm, { spotifyLinked: true });

		await fireEvent.input(screen.getByLabelText('Room name'), {
			target: { value: 'Friday vibes' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		expect(toast.error).toHaveBeenCalledWith('Please enter your display name.');
		expect(apiClient.createRoom).not.toHaveBeenCalled();
	});

	it('accepts room name at max length boundary (40 chars)', async () => {
		vi.mocked(apiClient.createRoom).mockResolvedValue({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'AB2CD3'
		});
		render(CreateRoomForm, { spotifyLinked: true });

		const roomName = 'A'.repeat(40);
		await fireEvent.input(screen.getByLabelText('Room name'), { target: { value: roomName } });
		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		await waitFor(() => expect(apiClient.createRoom).toHaveBeenCalledTimes(1));
		expect(apiClient.createRoom).toHaveBeenCalledWith(
			expect.objectContaining({
				name: roomName
			})
		);
	});

	it('shows an error when room name exceeds max length', async () => {
		render(CreateRoomForm, { spotifyLinked: true });

		await fireEvent.input(screen.getByLabelText('Room name'), {
			target: { value: 'B'.repeat(41) }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		expect(toast.error).toHaveBeenCalledWith('Room name must be 40 characters or fewer.');
		expect(apiClient.createRoom).not.toHaveBeenCalled();
	});

	it('disables submit button for unsupported provider values', async () => {
		render(CreateRoomForm, { spotifyLinked: true });
		const providerSelect = screen.getByLabelText('Music provider') as HTMLSelectElement;
		const unsupportedOption = document.createElement('option');
		unsupportedOption.value = 'invalid-provider';
		unsupportedOption.text = 'Invalid';
		providerSelect.append(unsupportedOption);

		await fireEvent.input(screen.getByLabelText('Room name'), {
			target: { value: 'Friday vibes' }
		});
		await fireEvent.change(providerSelect, { target: { value: 'invalid-provider' } });

		const submitButton = screen.getByRole('button', { name: 'Create room' }) as HTMLButtonElement;
		expect(submitButton.disabled).toBe(true);
		expect(apiClient.createRoom).not.toHaveBeenCalled();
	});

	it('submits trimmed values and emits success payload', async () => {
		vi.mocked(apiClient.createRoom).mockResolvedValue({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'AB2CD3'
		});
		const onSuccess = vi.fn();
		render(CreateRoomForm, { onsuccess: onSuccess, spotifyLinked: true });

		const displayNameInput = screen.getByLabelText('Your display name');
		const roomNameInput = screen.getByLabelText('Room name');

		await fireEvent.input(displayNameInput, { target: { value: '  Alice Cooper  ' } });
		await fireEvent.input(roomNameInput, { target: { value: '  Friday vibes  ' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		await waitFor(() => expect(apiClient.createRoom).toHaveBeenCalledTimes(1));

		expect(saveSessionDisplayName).toHaveBeenCalledWith('Alice Cooper');
		expect(apiClient.createRoom).toHaveBeenCalledWith({
			name: 'Friday vibes',
			user_id: 'U_TESTUSER1',
			display_name: 'Alice Cooper',
			supported_provider_id: 'spotify'
		});
		expect(recordRecentRoom).toHaveBeenCalledWith({
			joinCode: 'AB2CD3',
			name: 'Friday vibes',
			isHost: true
		});
		expect(toast.success).toHaveBeenCalledWith('Room created');
		expect(onSuccess).toHaveBeenCalledWith({ roomId: 'room-1', joinCode: 'AB2CD3' });
	});

	it('shows busy state while create request is in flight', async () => {
		const request = deferred<{
			success: boolean;
			message: string;
			room_id: string;
			join_code: string;
		}>();
		vi.mocked(apiClient.createRoom).mockReturnValue(request.promise);

		render(CreateRoomForm, { spotifyLinked: true });

		const displayNameInput = screen.getByLabelText('Your display name');
		const roomNameInput = screen.getByLabelText('Room name');
		await fireEvent.input(roomNameInput, { target: { value: 'Friday vibes' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Create room' }));

		expect((screen.getByRole('button', { name: 'Creating…' }) as HTMLButtonElement).disabled).toBe(
			true
		);
		expect((displayNameInput as HTMLInputElement).disabled).toBe(true);
		expect((roomNameInput as HTMLInputElement).disabled).toBe(true);

		request.resolve({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'AB2CD3'
		});

		await waitFor(() =>
			expect(
				(screen.getByRole('button', { name: 'Create room' }) as HTMLButtonElement).disabled
			).toBe(false)
		);
	});

	it('ignores duplicate form submits while request is pending', async () => {
		const request = deferred<{
			success: boolean;
			message: string;
			room_id: string;
			join_code: string;
		}>();
		vi.mocked(apiClient.createRoom).mockReturnValue(request.promise);

		render(CreateRoomForm, { spotifyLinked: true });
		await fireEvent.input(screen.getByLabelText('Room name'), {
			target: { value: 'Friday vibes' }
		});

		const submitButton = screen.getByRole('button', { name: 'Create room' });
		const form = submitButton.closest('form');
		expect(form).not.toBeNull();
		if (!form) return;

		await fireEvent.submit(form);
		await fireEvent.submit(form);

		expect(apiClient.createRoom).toHaveBeenCalledTimes(1);

		request.resolve({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: 'AB2CD3'
		});
		await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Room created'));
	});
});
