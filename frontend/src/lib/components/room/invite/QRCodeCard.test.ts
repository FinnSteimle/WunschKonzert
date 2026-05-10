import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { mockToDataURL } = vi.hoisted(() => ({
	mockToDataURL: vi.fn(() => Promise.resolve('data:image/png;base64,xx'))
}));

vi.mock('qrcode', () => ({
	default: {
		toDataURL: mockToDataURL
	}
}));

import QRCodeCard from './QRCodeCard.svelte';

describe('QRCodeCard', () => {
	it('shows copy when invite url empty', () => {
		render(QRCodeCard, { inviteUrl: '' });
		expect(screen.getByText('Invite link not ready yet.')).toBeTruthy();
	});

	it('generates and shows QR image', async () => {
		mockToDataURL.mockResolvedValueOnce('data:image/png;base64,xx');

		render(QRCodeCard, { inviteUrl: 'https://join.example/room/x' });

		await waitFor(() => {
			expect(screen.getByRole('img', { name: 'QR code for room invite' })).toBeTruthy();
		});

		expect(mockToDataURL).toHaveBeenCalledWith('https://join.example/room/x', expect.any(Object));
	});

	it('stays on loading placeholder after qrcode rejects', async () => {
		mockToDataURL.mockRejectedValueOnce(new Error('offline'));
		render(QRCodeCard, { inviteUrl: 'https://join.example/y' });

		await waitFor(() => {
			expect(screen.getByLabelText('Generating QR code')).toBeTruthy();
		});

		expect(screen.queryByRole('img', { name: 'QR code for room invite' })).toBeNull();
	});
});
