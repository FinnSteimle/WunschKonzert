import { render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RecentRoomsPanel from './RecentRoomsPanel.svelte';
import { getRecentRooms, syncRecentRoomsAvailability } from '$lib/session/recentRooms';
import type { RecentRoomEntry } from '$lib/session/recentRooms';

vi.mock('$app/environment', () => ({
	browser: true
}));

vi.mock('$app/paths', () => ({
	resolve: vi.fn((path: string, params?: { roomId?: string }) =>
		path === '/room/[roomId]' && params?.roomId ? `/room/${params.roomId}` : path
	)
}));

vi.mock('$lib/session/recentRooms', () => ({
	getRecentRooms: vi.fn(),
	syncRecentRoomsAvailability: vi.fn()
}));

const rooms: RecentRoomEntry[] = [
	{ joinCode: 'AB2CD3', name: 'Friday vibes', isHost: true, visitedAt: 1 },
	{ joinCode: 'ZX9WV8', name: 'Chill session', isHost: false, visitedAt: 2 }
];

describe('RecentRoomsPanel', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders nothing when there are no recent rooms', () => {
		vi.mocked(getRecentRooms).mockReturnValue([]);
		vi.mocked(syncRecentRoomsAvailability).mockResolvedValue([]);

		const { container } = render(RecentRoomsPanel);

		expect(container.textContent).toBe('');
	});

	it('renders recent room entries with names and join codes', async () => {
		vi.mocked(getRecentRooms).mockReturnValue(rooms);
		vi.mocked(syncRecentRoomsAvailability).mockResolvedValue(rooms);

		render(RecentRoomsPanel);

		await waitFor(() => expect(screen.getByText('Friday vibes')).toBeTruthy());
		expect(screen.getByText('Chill session')).toBeTruthy();
		expect(screen.getByText('AB2CD3')).toBeTruthy();
		expect(screen.getByText('ZX9WV8')).toBeTruthy();
	});

	it('shows Host badge only for rooms where user is host', async () => {
		vi.mocked(getRecentRooms).mockReturnValue(rooms);
		vi.mocked(syncRecentRoomsAvailability).mockResolvedValue(rooms);

		render(RecentRoomsPanel);

		await waitFor(() => expect(screen.getByText('Friday vibes')).toBeTruthy());
		const badges = screen.getAllByText('Host');
		expect(badges).toHaveLength(1);
	});

	it('links each entry to the correct room route', async () => {
		vi.mocked(getRecentRooms).mockReturnValue(rooms);
		vi.mocked(syncRecentRoomsAvailability).mockResolvedValue(rooms);

		render(RecentRoomsPanel);

		await waitFor(() => expect(screen.getByText('Friday vibes')).toBeTruthy());
		const links = screen.getAllByRole('link');
		expect(links[0].getAttribute('href')).toBe('/room/AB2CD3');
		expect(links[1].getAttribute('href')).toBe('/room/ZX9WV8');
	});

	it('removes stale entries after availability sync', async () => {
		vi.mocked(getRecentRooms).mockReturnValue(rooms);
		vi.mocked(syncRecentRoomsAvailability).mockResolvedValue([rooms[1]]);

		render(RecentRoomsPanel);

		await waitFor(() => expect(screen.queryByText('Friday vibes')).toBeNull());
		expect(screen.getByText('Chill session')).toBeTruthy();
	});

	it('renders heading and description text', async () => {
		vi.mocked(getRecentRooms).mockReturnValue(rooms);
		vi.mocked(syncRecentRoomsAvailability).mockResolvedValue(rooms);

		render(RecentRoomsPanel);

		await waitFor(() => expect(screen.getByText('Recent rooms')).toBeTruthy());
		expect(screen.getByText(/Jump back to a room/)).toBeTruthy();
	});
});
