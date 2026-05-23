import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import HostTransferPanel from './HostTransferPanel.svelte';
import type { RoomStateDto } from '$lib/types/api';

function makeRoomState(overrides: Partial<RoomStateDto> = {}): RoomStateDto {
	return {
		room: {
			roomId: 'room-1',
			joinCode: 'AB2CD3',
			name: 'Test',
			status: 'active',
			createdAt: '2025-01-01T00:00:00Z',
			supportedProviderId: 'spotify'
		},
		host: { userId: 'host-1', displayName: 'Host', createdAt: '2025-01-01T00:00:00Z' },
		users: [
			{
				user: { userId: 'host-1', displayName: 'Host', createdAt: '2025-01-01T00:00:00Z' },
				membership: {
					joinedAt: '2025-01-01T00:00:00Z',
					leftAt: null,
					membershipStatus: 'active'
				}
			},
			{
				user: { userId: 'guest-1', displayName: 'Guest', createdAt: '2025-01-01T00:00:00Z' },
				membership: {
					joinedAt: '2025-01-01T00:00:00Z',
					leftAt: null,
					membershipStatus: 'active'
				}
			}
		],
		queue: [],
		...overrides
	};
}

const transfer = {
	transferId: 't-1',
	fromUserId: 'host-1',
	toUserId: 'guest-1',
	createdAt: '2025-01-01T00:00:00Z'
};

describe('HostTransferPanel', () => {
	it('shows invitee actions for the invited user', async () => {
		const onAccept = vi.fn();
		const onReject = vi.fn();
		render(HostTransferPanel, {
			transfer,
			roomState: makeRoomState(),
			currentUserId: 'guest-1',
			providerLinked: true,
			onAccept,
			onReject
		});

		expect(screen.getByText('Host invitation')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Accept host role' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Decline' }));
		expect(onAccept).toHaveBeenCalledOnce();
		expect(onReject).toHaveBeenCalledOnce();
	});

	it('shows pending message for inviter without accept buttons', () => {
		render(HostTransferPanel, {
			transfer,
			roomState: makeRoomState(),
			currentUserId: 'host-1'
		});

		expect(screen.getByText('Host transfer pending')).toBeTruthy();
		expect(screen.getByText(/Waiting for Guest/)).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Accept host role' })).toBeNull();
	});

	it('requires Spotify link before accept when not linked', () => {
		render(HostTransferPanel, {
			transfer,
			roomState: makeRoomState(),
			currentUserId: 'guest-1',
			providerLinked: false
		});

		expect((screen.getByRole('button', { name: 'Accept host role' }) as HTMLButtonElement).disabled).toBe(
			true
		);
		expect(screen.getByRole('button', { name: 'Link Spotify account' })).toBeTruthy();
	});
});
