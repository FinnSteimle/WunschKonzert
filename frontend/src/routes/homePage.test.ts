import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HomePage from './+page.svelte';
import { getRecentRooms, syncRecentRoomsAvailability } from '$lib/session/recentRooms';

vi.mock('$app/environment', () => ({
	browser: true
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: vi.fn((path: string, params?: { roomId?: string }) =>
		path === '/room/[roomId]' && params?.roomId ? `/room/${params.roomId}` : path
	)
}));

vi.mock('$lib/session/userSession', () => ({
	getOrCreateSessionUser: vi.fn(() => ({ userId: 'U_1', displayName: 'Alice' })),
	saveSessionDisplayName: vi.fn(),
	generateRandomDisplayName: vi.fn(() => 'DJ Fox')
}));

vi.mock('$lib/session/recentRooms', () => ({
	getRecentRooms: vi.fn(),
	syncRecentRoomsAvailability: vi.fn(),
	recordRecentRoom: vi.fn(),
	removeRecentRoom: vi.fn(),
	isJoinFailureForRemovedRoom: vi.fn()
}));

vi.mock('svelte-sonner', () => ({
	toast: { error: vi.fn() }
}));

describe('+page.svelte (home)', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(getRecentRooms).mockReturnValue([]);
		vi.mocked(syncRecentRoomsAvailability).mockResolvedValue([]);
	});

	it('renders the app heading', () => {
		render(HomePage);

		expect(screen.getByText('WunschKonzert')).toBeTruthy();
	});

	it('renders the join-with-code card', () => {
		render(HomePage);

		expect(screen.getByText('Join with code')).toBeTruthy();
		expect(screen.getByText('Enter the 6-character code from the host.')).toBeTruthy();
	});

	it('has a Create a room link', () => {
		render(HomePage);

		const link = screen.getByRole('link', { name: 'Create a room' });
		expect(link).toBeTruthy();
		expect(link.getAttribute('href')).toBe('/create');
	});

	it('renders the room code input field', () => {
		render(HomePage);

		expect(screen.getByLabelText('Room code')).toBeTruthy();
	});

	it('shows hosting prompt text', () => {
		render(HomePage);

		expect(screen.getByText('Hosting a session?')).toBeTruthy();
	});
});
