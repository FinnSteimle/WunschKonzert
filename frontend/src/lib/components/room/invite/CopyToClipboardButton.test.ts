import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CopyToClipboardButton from './CopyToClipboardButton.svelte';
import { toast } from 'svelte-sonner';

vi.mock('svelte-sonner', () => ({
	toast: {
		error: vi.fn()
	}
}));

describe('CopyToClipboardButton', () => {
	let writeTextMock: ReturnType<typeof vi.fn>;

	beforeEach(() => {
		vi.useFakeTimers();
		vi.clearAllMocks();
		writeTextMock = vi.fn();
		Object.defineProperty(navigator, 'clipboard', {
			value: { writeText: writeTextMock },
			configurable: true
		});
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('copies text and shows temporary copied state', async () => {
		writeTextMock.mockResolvedValue(undefined);

		render(CopyToClipboardButton, {
			textToCopy: 'AB12CD',
			label: 'Copy invite code'
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Copy invite code' }));

		expect(writeTextMock).toHaveBeenCalledWith('AB12CD');
		expect(screen.getByRole('button', { name: 'Copied to clipboard' })).toBeTruthy();

		vi.advanceTimersByTime(2000);

		await waitFor(() =>
			expect(screen.getByRole('button', { name: 'Copy invite code' })).toBeTruthy()
		);
	});

	it('shows error toast if clipboard write fails', async () => {
		writeTextMock.mockRejectedValue(new Error('No clipboard'));

		render(CopyToClipboardButton, {
			textToCopy: 'AB12CD',
			label: 'Copy invite code'
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Copy invite code' }));

		await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Could not copy to clipboard'));
		expect(screen.getByRole('button', { name: 'Copy invite code' })).toBeTruthy();
	});
});
