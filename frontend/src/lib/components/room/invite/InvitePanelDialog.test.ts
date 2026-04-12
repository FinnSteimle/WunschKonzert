import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import InvitePanelDialog from './InvitePanelDialog.svelte';

vi.mock('svelte-sonner', () => ({
	toast: { error: vi.fn() }
}));

vi.mock('$lib/components/room/invite/QRCodeCard.svelte', () => ({
	default: function QRCodeCardStub() {}
}));

describe('InvitePanelDialog', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders a trigger button with the default label', () => {
		render(InvitePanelDialog, {
			joinCode: 'AB2CD3',
			inviteUrl: 'https://example.com/room/AB2CD3'
		});

		expect(screen.getByRole('button', { name: 'Invite' })).toBeTruthy();
	});

	it('renders a trigger button with a custom label', () => {
		render(InvitePanelDialog, {
			joinCode: 'AB2CD3',
			inviteUrl: 'https://example.com/room/AB2CD3',
			buttonLabel: 'Share room'
		});

		expect(screen.getByRole('button', { name: 'Share room' })).toBeTruthy();
	});

	it('opens dialog with invite content when trigger is clicked', async () => {
		render(InvitePanelDialog, {
			joinCode: 'AB2CD3',
			inviteUrl: 'https://example.com/room/AB2CD3'
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

		await waitFor(() => expect(screen.getByText('Invite guests')).toBeTruthy());
		expect(screen.getByText(/Share the code, link, or QR code/)).toBeTruthy();
		expect(screen.getByText('AB2CD3')).toBeTruthy();
	});
});
