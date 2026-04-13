import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import InvitePanel from './InvitePanel.svelte';

vi.mock('svelte-sonner', () => ({
	toast: { error: vi.fn() }
}));

vi.mock('$lib/components/room/invite/QRCodeCard.svelte', () => ({
	default: function QRCodeCardStub() {}
}));

describe('InvitePanel', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('displays the join code in a badge', () => {
		render(InvitePanel, { joinCode: 'AB2CD3', inviteUrl: 'https://example.com/room/AB2CD3' });

		expect(screen.getByText('AB2CD3')).toBeTruthy();
	});

	it('displays the invite URL in a readonly input', () => {
		render(InvitePanel, { joinCode: 'AB2CD3', inviteUrl: 'https://example.com/room/AB2CD3' });

		const input = screen.getByDisplayValue('https://example.com/room/AB2CD3') as HTMLInputElement;
		expect(input).toBeTruthy();
		expect(input.readOnly).toBe(true);
	});

	it('renders a Copy code button', () => {
		render(InvitePanel, { joinCode: 'AB2CD3', inviteUrl: 'https://example.com/room/AB2CD3' });

		expect(screen.getByRole('button', { name: 'Copy code' })).toBeTruthy();
	});

	it('renders a Copy link button', () => {
		render(InvitePanel, { joinCode: 'AB2CD3', inviteUrl: 'https://example.com/room/AB2CD3' });

		expect(screen.getByRole('button', { name: 'Copy link' })).toBeTruthy();
	});

	it('renders section headings for code and link', () => {
		render(InvitePanel, { joinCode: 'AB2CD3', inviteUrl: 'https://example.com/room/AB2CD3' });

		expect(screen.getByText('Room code')).toBeTruthy();
		expect(screen.getByText('Invite link')).toBeTruthy();
	});
});
