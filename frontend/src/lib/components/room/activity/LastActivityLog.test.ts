import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LastActivityLog from './LastActivityLog.svelte';
import type { LastActivityDto, RoomStateDto } from '$lib/types/api';

const roomState: RoomStateDto = {
	room: {
		roomId: 'room-1',
		joinCode: 'AB2CD3',
		name: 'Friday vibes',
		status: 'active',
		createdAt: '2025-01-01T00:00:00Z',
		supportedProviderId: 'spotify'
	},
	host: {
		userId: 'U_HOST',
		displayName: 'Host',
		createdAt: '2025-01-01T00:00:00Z'
	},
	users: [],
	queue: [
		{
			queueEntryId: 'q1',
			track: {
				trackId: 't1',
				providerTrackId: 'spotify:t1',
				title: 'Song',
				artist: 'Artist',
				album: 'Album',
				duration: 180,
				coverUrl: '',
				deepLink: ''
			},
			addedBy: {
				userId: 'U_ALICE',
				displayName: 'Alice'
			},
			queuedAt: '2025-01-01T00:00:00Z',
			position: 1,
			status: 'queued',
			voteScore: 0,
			orderRank: 1,
			feedback: []
		}
	]
};

describe('LastActivityLog', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2025-06-15T12:00:00.000Z'));
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('shows an empty state when no unread activities exist', async () => {
		render(LastActivityLog, { activities: [], roomState });
		await fireEvent.click(screen.getByRole('button', { name: 'Unread room activity: 0' }));

		expect(screen.getByText('No unread activity.')).toBeTruthy();
	});

	it('renders unread activity text with track titles and relative time', async () => {
		const activities: LastActivityDto[] = [
			{
				type: 'track_added',
				userId: 'U_ALICE',
				username: 'Alice',
				at: '2025-06-15T11:55:00.000Z',
				queueEntryId: 'q1'
			}
		];

		render(LastActivityLog, { activities, roomState });
		expect(screen.getByRole('button', { name: 'Unread room activity: 1' })).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Unread room activity: 1' }));

		expect(screen.getByRole('list', { name: 'Unread room activity' })).toBeTruthy();
		expect(screen.getByText('Alice added "Song"')).toBeTruthy();
		expect(screen.getByText('5m ago')).toBeTruthy();
	});

	it('renders user joined activity', async () => {
		const activities: LastActivityDto[] = [
			{
				type: 'user_joined',
				userId: 'U_BOB',
				username: 'Bob',
				at: '2025-06-15T11:59:00.000Z'
			}
		];

		render(LastActivityLog, { activities, roomState });
		expect(screen.getByRole('button', { name: 'Unread room activity: 1' })).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Unread room activity: 1' }));

		expect(screen.getByRole('list', { name: 'Unread room activity' })).toBeTruthy();
		expect(screen.getByText('Bob joined the room')).toBeTruthy();
		expect(screen.getByText('1m ago')).toBeTruthy();
	});

	it('highlights important host transfer activity', async () => {
		render(LastActivityLog, {
			activities: [
				{
					type: 'host_transfer_completed',
					userId: 'U_ALICE',
					username: 'Alice',
					at: '2025-06-15T12:00:00.000Z'
				}
			],
			roomState
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Unread room activity: 1' }));
		expect(screen.getByText('Alice became the host')).toBeTruthy();
		expect(screen.getByText('Alice became the host').closest('li')?.className).toContain(
			'border-violet-500/40'
		);
	});

	it('marks unread activities as read after closing the popup', async () => {
		const onMarkRead = vi.fn();
		render(LastActivityLog, {
			activities: [
				{
					type: 'track_added',
					userId: 'U_ALICE',
					username: 'Alice',
					at: '2025-06-15T11:55:00.000Z',
					queueEntryId: 'q1'
				}
			],
			roomState,
			onMarkRead
		});

		const trigger = screen.getByRole('button', { name: 'Unread room activity: 1' });
		await fireEvent.click(trigger);
		expect(onMarkRead).not.toHaveBeenCalled();
		await fireEvent.click(trigger);

		expect(onMarkRead).toHaveBeenCalledOnce();
	});

	it('shows 99+ when unread activity reaches 100 items', () => {
		const activities: LastActivityDto[] = Array.from({ length: 100 }, (_, index) => ({
			type: 'user_left',
			userId: `U_${index}`,
			username: `User ${index}`,
			at: `2025-06-15T11:${String(index % 60).padStart(2, '0')}:00.000Z`
		}));

		render(LastActivityLog, { activities, roomState });

		expect(screen.getByRole('button', { name: 'Unread room activity: 99+' })).toBeTruthy();
		expect(screen.getByText('99+')).toBeTruthy();
	});
});
