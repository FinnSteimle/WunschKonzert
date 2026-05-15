import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import SystemMessagesList from './SystemMessagesList.svelte';
import type { SystemMessageDto } from '$lib/types/api';

const messages: SystemMessageDto[] = [
	{ id: 'm1', text: '2 songs removed during host transfer.', at: '2025-01-01T00:00:00Z' },
	{ id: 'm2', text: 'Queue synced to new host library.', at: '2025-01-01T00:01:00Z' }
];

describe('SystemMessagesList', () => {
	it('renders nothing when messages array is empty', () => {
		render(SystemMessagesList, { messages: [] });
		expect(screen.queryByRole('list', { name: 'Room notifications' })).toBeNull();
	});

	it('renders each system message in a list', () => {
		render(SystemMessagesList, { messages });

		const list = screen.getByRole('list', { name: 'Room notifications' });
		expect(list).toBeTruthy();
		expect(screen.getByText(messages[0].text)).toBeTruthy();
		expect(screen.getByText(messages[1].text)).toBeTruthy();
	});
});
