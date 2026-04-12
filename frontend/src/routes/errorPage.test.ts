import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ErrorPage from './+error.svelte';

vi.mock('$app/state', () => ({
	page: {
		status: 404,
		error: { message: 'Page not found' }
	}
}));

describe('+error.svelte', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the error heading', () => {
		render(ErrorPage);

		expect(screen.getByText('Something went wrong')).toBeTruthy();
	});

	it('displays the HTTP status code', () => {
		render(ErrorPage);

		expect(screen.getByText('HTTP 404')).toBeTruthy();
	});

	it('displays the error message', () => {
		render(ErrorPage);

		expect(screen.getByText('Page not found')).toBeTruthy();
	});

	it('has a link back to the home page', () => {
		render(ErrorPage);

		const link = screen.getByRole('link', { name: 'Back home' });
		expect(link).toBeTruthy();
		expect(link.getAttribute('href')).toBe('/');
	});
});
