import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DeleteRoomButton from './DeleteRoomButton.svelte';
import { apiClient } from '$lib/api/client';
import { toast } from 'svelte-sonner';

vi.mock('$lib/api/client', () => ({
	apiClient: {
		deleteRoom: vi.fn()
	}
}));

vi.mock('svelte-sonner', () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn()
	}
}));

describe('DeleteRoomButton', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders a delete room button', () => {
		render(DeleteRoomButton, { roomId: 'room-1', userId: 'user-1' });
		expect(screen.getByRole('button', { name: 'Delete room' })).toBeTruthy();
	});

	it('disables the button when disabled prop is true', () => {
		render(DeleteRoomButton, { roomId: 'room-1', userId: 'user-1', disabled: true });
		expect(
			(screen.getByRole('button', { name: 'Delete room' }) as HTMLButtonElement).disabled
		).toBe(true);
	});

	it('opens confirmation dialog on click', async () => {
		render(DeleteRoomButton, { roomId: 'room-1', userId: 'user-1' });
		await fireEvent.click(screen.getByRole('button', { name: 'Delete room' }));

		expect(screen.getByText('Delete this room?')).toBeTruthy();
		expect(screen.getByText(/This stops playback/)).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Delete forever' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();
	});

	it('calls deleteRoom API and shows success toast on confirm', async () => {
		vi.mocked(apiClient.deleteRoom).mockResolvedValue({
			success: true,
			message: 'ok',
			room_id: 'room-1',
			join_code: null
		});

		render(DeleteRoomButton, { roomId: 'room-1', userId: 'user-1' });
		await fireEvent.click(screen.getByRole('button', { name: 'Delete room' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Delete forever' }));

		await waitFor(() =>
			expect(apiClient.deleteRoom).toHaveBeenCalledWith({
				room_id: 'room-1',
				user_id: 'user-1'
			})
		);
		await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Room deleted'));
	});

	it('shows error toast when delete fails', async () => {
		vi.mocked(apiClient.deleteRoom).mockRejectedValue(new Error('Not authorized'));

		render(DeleteRoomButton, { roomId: 'room-1', userId: 'user-1' });
		await fireEvent.click(screen.getByRole('button', { name: 'Delete room' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Delete forever' }));

		await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Not authorized'));
	});

	it('shows generic error when non-Error is thrown', async () => {
		vi.mocked(apiClient.deleteRoom).mockRejectedValue('kaboom');

		render(DeleteRoomButton, { roomId: 'room-1', userId: 'user-1' });
		await fireEvent.click(screen.getByRole('button', { name: 'Delete room' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Delete forever' }));

		await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Could not delete room'));
	});

	it('shows Deleting… text while busy', async () => {
		let resolveDelete!: (v: { success: boolean; message: string; room_id: string | null; join_code: string | null }) => void;
		vi.mocked(apiClient.deleteRoom).mockReturnValue(
			new Promise((res) => {
				resolveDelete = res;
			})
		);

		render(DeleteRoomButton, { roomId: 'room-1', userId: 'user-1' });
		await fireEvent.click(screen.getByRole('button', { name: 'Delete room' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Delete forever' }));

		await waitFor(() => expect(screen.getByText('Deleting…')).toBeTruthy());

		resolveDelete({ success: true, message: 'ok', room_id: 'room-1', join_code: null });

		await waitFor(() => expect(toast.success).toHaveBeenCalled());
	});
});
