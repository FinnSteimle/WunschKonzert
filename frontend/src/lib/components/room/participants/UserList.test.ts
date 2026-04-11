import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import UserList from './UserList.svelte';
import type { RoomStateDto } from '$lib/types/api';

function makeUsers(
	...specs: Array<{ userId: string; displayName: string; leftAt?: string | null }>
): RoomStateDto['users'] {
	return specs.map((s) => ({
		user: { userId: s.userId, displayName: s.displayName, createdAt: '2025-01-01T00:00:00Z' },
		membership: {
			joinedAt: '2025-01-01T00:00:00Z',
			leftAt: s.leftAt ?? null,
			membershipStatus: 'active'
		}
	}));
}

describe('UserList', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows empty state when no active users', () => {
		const users = makeUsers({ userId: 'u1', displayName: 'Alice', leftAt: '2025-01-02T00:00:00Z' });
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u2' });

		expect(screen.getByText('No listeners yet')).toBeTruthy();
	});

	it('renders active users', () => {
		const users = makeUsers(
			{ userId: 'u1', displayName: 'Alice' },
			{ userId: 'u2', displayName: 'Bob' }
		);
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u2' });

		expect(screen.getByText('Alice')).toBeTruthy();
		expect(screen.getByText('Bob')).toBeTruthy();
	});

	it('filters out users who have left', () => {
		const users = makeUsers(
			{ userId: 'u1', displayName: 'Alice' },
			{ userId: 'u2', displayName: 'Gone', leftAt: '2025-01-02T00:00:00Z' }
		);
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u1' });

		expect(screen.getByText('Alice')).toBeTruthy();
		expect(screen.queryByText('Gone')).toBeNull();
	});

	it('shows Host badge for the host user', () => {
		const users = makeUsers(
			{ userId: 'u1', displayName: 'Alice' },
			{ userId: 'u2', displayName: 'Bob' }
		);
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u2' });

		expect(screen.getByText('Host')).toBeTruthy();
	});

	it('shows You badge for the current user', () => {
		const users = makeUsers({ userId: 'u1', displayName: 'Alice' });
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u1' });

		expect(screen.getByText('You')).toBeTruthy();
	});

	it('shows edit button for current user', () => {
		const users = makeUsers({ userId: 'u1', displayName: 'Alice' });
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u1' });

		expect(screen.getByRole('button', { name: 'Edit display name' })).toBeTruthy();
	});

	it('does not show edit button for other users', () => {
		const users = makeUsers(
			{ userId: 'u1', displayName: 'Alice' },
			{ userId: 'u2', displayName: 'Bob' }
		);
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u2' });

		const editButtons = screen.getAllByRole('button', { name: 'Edit display name' });
		expect(editButtons).toHaveLength(1);
	});

	it('calls onEditSelf when edit button is clicked', async () => {
		const onEditSelf = vi.fn();
		const users = makeUsers({ userId: 'u1', displayName: 'Alice' });
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u1', onEditSelf });

		await fireEvent.click(screen.getByRole('button', { name: 'Edit display name' }));

		expect(onEditSelf).toHaveBeenCalledOnce();
	});

	it('highlights current user row with aria-current', () => {
		const users = makeUsers(
			{ userId: 'u1', displayName: 'Alice' },
			{ userId: 'u2', displayName: 'Bob' }
		);
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u1' });

		const items = screen.getAllByRole('listitem');
		const selfItem = items.find((item) => item.textContent?.includes('Alice'));
		expect(selfItem?.getAttribute('aria-current')).toBe('true');
	});

	it('has accessible list with correct aria-label', () => {
		const users = makeUsers({ userId: 'u1', displayName: 'Alice' });
		render(UserList, { users, hostUserId: 'u1', currentUserId: 'u1' });

		expect(screen.getByRole('list', { name: 'Room members' })).toBeTruthy();
	});
});
