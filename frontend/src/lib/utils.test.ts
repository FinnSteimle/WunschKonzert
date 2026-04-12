import { describe, expect, it } from 'vitest';
import { cn } from './utils';

describe('cn', () => {
	it('merges class names', () => {
		expect(cn('text-sm', 'font-bold')).toBe('text-sm font-bold');
	});

	it('handles conditional classes', () => {
		expect(cn('text-sm', false && 'hidden', 'flex')).toBe('text-sm flex');
	});

	it('deduplicates conflicting Tailwind classes', () => {
		expect(cn('px-2', 'px-4')).toBe('px-4');
	});

	it('handles undefined and null values', () => {
		expect(cn('text-sm', undefined, null, 'flex')).toBe('text-sm flex');
	});

	it('returns empty string for no inputs', () => {
		expect(cn()).toBe('');
	});

	it('merges array inputs', () => {
		expect(cn(['text-sm', 'font-bold'], 'flex')).toBe('text-sm font-bold flex');
	});

	it('resolves conflicting text color classes', () => {
		expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
	});
});
