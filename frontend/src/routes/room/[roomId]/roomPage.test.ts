import { render, screen, waitFor } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import RoomPage from './+page.svelte';
import { roomStore } from '$lib/stores/room';
import { apiClient } from '$lib/api/client';
import { getOrCreateSessionUser, saveSessionDisplayName } from '$lib/session/userSession';
import { isJoinFailureForRemovedRoom, removeRecentRoom } from '$lib/session/recentRooms';
import { page } from '$app/state';

vi.mock('$app/environment', () => ({ browser: true }));

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

vi.mock('$app/paths', () => ({
	resolve: vi.fn((path: string) => path)
}));

vi.mock('$app/state', () => ({
	page: {
		params: { roomId: 'AB2CD3' },
		url: { origin: 'http://localhost:5173' }
	}
}));

vi.mock('$lib/api/client', () => ({
	apiClient: {
		joinRoom: vi.fn(),
		searchSongs: vi.fn()
	}
}));

vi.mock('$lib/session/userSession', () => ({
	getOrCreateSessionUser: vi.fn(),
	saveSessionDisplayName: vi.fn(),
	generateRandomDisplayName: vi.fn(() => 'DJ Fox')
}));

vi.mock('$lib/session/recentRooms', () => ({
	isJoinFailureForRemovedRoom: vi.fn(),
	recordRecentRoom: vi.fn(),
	removeRecentRoom: vi.fn()
}));

vi.mock('svelte-sonner', () => ({
	toast: {
		error: vi.fn(),
		success: vi.fn(),
		message: vi.fn()
	}
}));

vi.mock('$lib/realtime/roomSocket', () => ({
	RoomSocketClient: class RoomSocketClientMock {
		connect = vi.fn();
		disconnect = vi.fn();
		isConnected = vi.fn(() => false);
		send = vi.fn();
		sendVote = vi.fn();
		addToQueue = vi.fn();
		removeQueueEntry = vi.fn();
		setPlayback = vi.fn();
		renameDisplayName = vi.fn();
		sendReplayVote = vi.fn();
	}
}));

vi.mock('$lib/components/room/invite/QRCodeCard.svelte', () => ({
	default: function QRCodeCardStub() {}
}));

describe('room/[roomId]/+page.svelte', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		roomStore.reset();
		vi.mocked(getOrCreateSessionUser).mockReturnValue({
			userId: 'U_USER1',
			displayName: 'Alice'
		});
		vi.mocked(isJoinFailureForRemovedRoom).mockReturnValue(false);
	});

	describe('invalid slug', () => {
		it('shows error for invalid room slug', async () => {
			(page as { params: Record<string, string> }).params = { roomId: '!!invalid!!' };

			render(RoomPage);

			await waitFor(() => {
				const state = get(roomStore);
				expect(state.error).toBe('This link is not a valid room or join code.');
			});
		});
	});

	describe('join code with stored display name (auto-join)', () => {
		beforeEach(() => {
			(page as { params: Record<string, string> }).params = { roomId: 'AB2CD3' };
		});

		it('calls joinRoom API with stored display name', async () => {
			vi.mocked(apiClient.joinRoom).mockResolvedValue({
				success: true,
				message: 'ok',
				room_id: 'room-1',
				join_code: 'AB2CD3'
			});

			render(RoomPage);

			await waitFor(() =>
				expect(apiClient.joinRoom).toHaveBeenCalledWith({
					join_code: 'AB2CD3',
					user_id: 'U_USER1',
					display_name: 'Alice'
				})
			);
		});

		it('shows error state when join fails', async () => {
			vi.mocked(apiClient.joinRoom).mockRejectedValue(new Error('Network error'));

			render(RoomPage);

			await waitFor(() => {
				const state = get(roomStore);
				expect(state.error).toBe('Network error');
				expect(state.loading).toBe(false);
			});
		});

		it('removes recent room when join failure indicates room was removed', async () => {
			vi.mocked(apiClient.joinRoom).mockRejectedValue(new Error('Room not found'));
			vi.mocked(isJoinFailureForRemovedRoom).mockReturnValue(true);

			render(RoomPage);

			await waitFor(() => expect(removeRecentRoom).toHaveBeenCalledWith('AB2CD3'));
		});

		it('shows error when join returns success:false', async () => {
			vi.mocked(apiClient.joinRoom).mockResolvedValue({
				success: false,
				message: 'Room is full',
				room_id: null,
				join_code: null
			});

			render(RoomPage);

			await waitFor(() => {
				const state = get(roomStore);
				expect(state.error).toBe('Room is full');
			});
		});
	});

	describe('join code without stored display name (link-join prompt)', () => {
		beforeEach(() => {
			(page as { params: Record<string, string> }).params = { roomId: 'AB2CD3' };
			vi.mocked(getOrCreateSessionUser).mockReturnValue({
				userId: 'U_USER1',
				displayName: ''
			});
		});

		it('shows the link-join form when display name is empty', async () => {
			render(RoomPage);

			await waitFor(() =>
				expect(
					screen.getByText('You opened a room link. Choose how your name appears to others.')
				).toBeTruthy()
			);
			expect(screen.getByText('Code AB2CD3')).toBeTruthy();
			expect(screen.getByRole('button', { name: 'Join room' })).toBeTruthy();
			expect(screen.getByRole('link', { name: 'Back home' })).toBeTruthy();
			expect((screen.getByRole('textbox', { name: 'Your display name' }) as HTMLInputElement).value).toBe(
				'DJ Fox'
			);
			expect(saveSessionDisplayName).toHaveBeenCalledWith('DJ Fox');
		});

		it('shows backend join errors inline after manual link join', async () => {
			vi.mocked(apiClient.joinRoom).mockRejectedValue(new Error('Room not found'));

			render(RoomPage);

			const input = await screen.findByRole('textbox', { name: 'Your display name' });
			await fireEvent.input(input, { target: { value: 'Guest' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Join room' }));

			await waitFor(() => expect(screen.getByText('Room not found')).toBeTruthy());
		});
	});

	describe('loading and room state display', () => {
		beforeEach(() => {
			(page as { params: Record<string, string> }).params = { roomId: 'AB2CD3' };
		});

		it('shows loading state initially during join', () => {
			vi.mocked(apiClient.joinRoom).mockReturnValue(new Promise(() => {}));

			render(RoomPage);

			expect(get(roomStore).loading).toBe(true);
		});

		it('shows room unavailable when error is set without room state', async () => {
			vi.mocked(apiClient.joinRoom).mockRejectedValue(new Error('Server down'));

			render(RoomPage);

			await waitFor(() => expect(screen.getByText('Room unavailable')).toBeTruthy());
			expect(screen.getByText('Server down')).toBeTruthy();
		});
	});

	describe('room state rendered (non-host)', () => {
		beforeEach(() => {
			(page as { params: Record<string, string> }).params = { roomId: 'AB2CD3' };
			vi.mocked(apiClient.joinRoom).mockResolvedValue({
				success: true,
				message: 'ok',
				room_id: 'room-1',
				join_code: 'AB2CD3'
			});
		});

		async function renderAndInjectState(options?: { withReplayVote?: boolean }) {
			render(RoomPage);
			await waitFor(() => expect(apiClient.joinRoom).toHaveBeenCalled());
			roomStore.setRoomState({
				room: {
					roomId: 'room-1',
					joinCode: 'AB2CD3',
					name: 'Friday vibes',
					status: 'active',
					createdAt: '2025-01-01T00:00:00Z'
				},
				host: {
					userId: 'U_HOST',
					displayName: 'Host User',
					createdAt: '2025-01-01T00:00:00Z'
				},
				users: [
					{
						user: { userId: 'U_USER1', displayName: 'Alice', createdAt: '2025-01-01T00:00:00Z' },
						membership: { joinedAt: '2025-01-01T00:00:00Z', leftAt: null, membershipStatus: 'active' }
					},
					{
						user: { userId: 'U_HOST', displayName: 'Host User', createdAt: '2025-01-01T00:00:00Z' },
						membership: { joinedAt: '2025-01-01T00:00:00Z', leftAt: null, membershipStatus: 'active' }
					}
				],
				queue: [
					{
						queueEntryId: 'q1',
						track: {
							trackId: 't1',
							providerTrackId: 'spotify:t1',
							title: 'Test Song',
							artist: 'Test Artist',
							album: 'Album',
							duration: 200,
							coverUrl: 'https://example.com/cover.jpg',
							deepLink: 'https://example.com/track/t1'
						},
						addedBy: { userId: 'U_USER1', displayName: 'Alice' },
						queuedAt: '2025-01-01T00:00:00Z',
						position: 0,
						status: 'queued',
						voteScore: 3,
						orderRank: 0,
						feedback: []
					}
				],
				playback: {
					state: 'playing',
					currentQueueEntryId: null,
					updatedAt: '2025-01-01T00:00:00Z',
					positionMs: 5000
				},
				...(options?.withReplayVote
					? {
							replayVote: {
								targetQueueEntryId: 'q-prev',
								track: {
									trackId: 't-prev',
									providerTrackId: 'spotify:t-prev',
									title: 'Encore',
									artist: 'Band',
									album: 'Album',
									duration: 200,
									coverUrl: '',
									deepLink: ''
								},
								voteCount: 0,
								voterUserIds: [],
								activeUserCount: 2,
								closesAt: '2030-01-01T00:00:00Z',
								status: 'open' as const
							}
						}
					: {})
			});
		}

		it('shows replay vote panel when server sends replayVote', async () => {
			await renderAndInjectState({ withReplayVote: true });

			await waitFor(() => expect(screen.getByText('Replay last track')).toBeTruthy());
			expect(screen.getByText(/Encore/)).toBeTruthy();
		});

		it('shows room name and join code in the header', async () => {
			await renderAndInjectState();

			await waitFor(() => expect(screen.getByText('Friday vibes')).toBeTruthy());
			expect(screen.getByText(/Code\s+AB2CD3/)).toBeTruthy();
		});

		it('shows Reconnecting badge when not connected', async () => {
			await renderAndInjectState();
			roomStore.setConnected(false);

			await waitFor(() => expect(screen.getByText('Reconnecting…')).toBeTruthy());
		});

		it('shows Live badge when connected', async () => {
			await renderAndInjectState();
			roomStore.setConnected(true);

			await waitFor(() => expect(screen.getByText('Live')).toBeTruthy());
		});

		it('shows Leave room button for non-host user', async () => {
			await renderAndInjectState();

			await waitFor(() => expect(screen.getByRole('button', { name: 'Leave room' })).toBeTruthy());
			expect(screen.queryByRole('button', { name: 'Delete room' })).toBeNull();
		});

		it('shows Home link for non-host user', async () => {
			await renderAndInjectState();

			await waitFor(() => expect(screen.getByRole('link', { name: 'Home' })).toBeTruthy());
		});

		it('renders section headings for Now playing, Queue, Add a song, Who is here', async () => {
			await renderAndInjectState();

			await waitFor(() => expect(screen.getByRole('heading', { name: 'Now playing' })).toBeTruthy());
			expect(screen.getByRole('heading', { name: 'Queue' })).toBeTruthy();
			expect(screen.getByRole('heading', { name: 'Add a song' })).toBeTruthy();
			expect(screen.getByRole('heading', { name: 'Who is here' })).toBeTruthy();
		});

		it('renders the Invite button', async () => {
			await renderAndInjectState();

			await waitFor(() => expect(screen.getByRole('button', { name: 'Invite' })).toBeTruthy());
		});
	});

	describe('room state rendered (host)', () => {
		beforeEach(() => {
			(page as { params: Record<string, string> }).params = { roomId: 'AB2CD3' };
			vi.mocked(getOrCreateSessionUser).mockReturnValue({
				userId: 'U_HOST',
				displayName: 'Host User'
			});
			vi.mocked(apiClient.joinRoom).mockResolvedValue({
				success: true,
				message: 'ok',
				room_id: 'room-1',
				join_code: 'AB2CD3'
			});
		});

		async function renderAsHostAndInjectState() {
			render(RoomPage);
			await waitFor(() => expect(apiClient.joinRoom).toHaveBeenCalled());
			roomStore.setRoomState({
				room: {
					roomId: 'room-1',
					joinCode: 'AB2CD3',
					name: 'Friday vibes',
					status: 'active',
					createdAt: '2025-01-01T00:00:00Z'
				},
				host: {
					userId: 'U_HOST',
					displayName: 'Host User',
					createdAt: '2025-01-01T00:00:00Z'
				},
				users: [],
				queue: [],
				playback: {
					state: 'paused',
					currentQueueEntryId: null,
					updatedAt: '2025-01-01T00:00:00Z',
					positionMs: 0
				}
			});
		}

		it('shows Delete room button for host user', async () => {
			await renderAsHostAndInjectState();

			await waitFor(() => expect(screen.getByRole('button', { name: 'Delete room' })).toBeTruthy());
			expect(screen.queryByRole('button', { name: 'Leave room' })).toBeNull();
		});
	});
});
