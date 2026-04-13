import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DisplayNameInput from './DisplayNameInput.svelte';
import { generateRandomDisplayName } from '$lib/session/userSession';

vi.mock('$lib/session/userSession', () => ({
	generateRandomDisplayName: vi.fn(() => 'BoldGoldFox'),
	getOrCreateSessionUser: vi.fn(() => ({ userId: 'U_1', displayName: '' })),
	saveSessionDisplayName: vi.fn()
}));

describe('DisplayNameInput', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
		vi.mocked(generateRandomDisplayName).mockReturnValue('BoldGoldFox');
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('renders a labelled text input', () => {
		render(DisplayNameInput, { id: 'wk-dn', value: '' });

		const input = screen.getByLabelText('Your display name') as HTMLInputElement;
		expect(input).toBeTruthy();
		expect(input.type).toBe('text');
		expect(input.placeholder).toBe('How others see you');
	});

	it('renders a randomize button', () => {
		render(DisplayNameInput, { id: 'wk-dn', value: '' });

		expect(screen.getByRole('button', { name: 'Randomize display name' })).toBeTruthy();
	});

	it('disables both input and randomize button when disabled', () => {
		render(DisplayNameInput, { id: 'wk-dn', value: '', disabled: true });

		expect((screen.getByLabelText('Your display name') as HTMLInputElement).disabled).toBe(true);
		expect(
			(screen.getByRole('button', { name: 'Randomize display name' }) as HTMLButtonElement).disabled
		).toBe(true);
	});

	it('sets the generated name as value after randomize animation completes', async () => {
		render(DisplayNameInput, { id: 'wk-dn', value: '' });

		await fireEvent.click(screen.getByRole('button', { name: 'Randomize display name' }));

		const target = 'BoldGoldFox';
		for (let i = 0; i < target.length; i++) {
			await vi.advanceTimersByTimeAsync(20);
		}
		await vi.advanceTimersByTimeAsync(50);

		const input = screen.getByLabelText('Your display name') as HTMLInputElement;
		expect(input.value).toBe('BoldGoldFox');
	});

	it('disables randomize button while animation is spinning', async () => {
		render(DisplayNameInput, { id: 'wk-dn', value: '' });

		await fireEvent.click(screen.getByRole('button', { name: 'Randomize display name' }));

		expect(
			(screen.getByRole('button', { name: 'Randomize display name' }) as HTMLButtonElement).disabled
		).toBe(true);

		const target = 'BoldGoldFox';
		for (let i = 0; i < target.length; i++) {
			await vi.advanceTimersByTimeAsync(20);
		}
		await vi.advanceTimersByTimeAsync(50);

		expect(
			(screen.getByRole('button', { name: 'Randomize display name' }) as HTMLButtonElement).disabled
		).toBe(false);
	});

	it('does not randomize when disabled prop is true', async () => {
		render(DisplayNameInput, { id: 'wk-dn', value: '', disabled: true });

		await fireEvent.click(screen.getByRole('button', { name: 'Randomize display name' }));

		await vi.advanceTimersByTimeAsync(500);
		expect(generateRandomDisplayName).not.toHaveBeenCalled();
	});

	it('applies maxlength to the input element', () => {
		render(DisplayNameInput, { id: 'wk-dn', value: '', maxlength: 60 });

		expect((screen.getByLabelText('Your display name') as HTMLInputElement).maxLength).toBe(60);
	});

	it('uses the correct id attribute on the input', () => {
		render(DisplayNameInput, { id: 'wk-custom-id', value: '' });

		expect(screen.getByLabelText('Your display name').id).toBe('wk-custom-id');
	});
});
