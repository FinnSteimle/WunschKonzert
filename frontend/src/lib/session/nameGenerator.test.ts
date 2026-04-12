import { describe, expect, it, vi } from 'vitest';
import { AUTO_GENERATED_NAME_RE, generateRandomDisplayName } from './nameGenerator';

describe('generateRandomDisplayName', () => {
	it('returns a deterministic composed name when random is mocked', () => {
		const randomSpy = vi
			.spyOn(Math, 'random')
			.mockReturnValueOnce(0)
			.mockReturnValueOnce(0)
			.mockReturnValueOnce(0);

		expect(generateRandomDisplayName()).toBe('CrazyPinkLizard');

		randomSpy.mockRestore();
	});

	it('always matches the generated-name regex', () => {
		for (let i = 0; i < 25; i += 1) {
			expect(AUTO_GENERATED_NAME_RE.test(generateRandomDisplayName())).toBe(true);
		}
	});
});

describe('AUTO_GENERATED_NAME_RE', () => {
	it('accepts names from known adjective/color/animal combinations', () => {
		expect(AUTO_GENERATED_NAME_RE.test('CrazyPinkLizard')).toBe(true);
		expect(AUTO_GENERATED_NAME_RE.test('MajesticTurquoiseDragon')).toBe(true);
	});

	it('rejects names outside the generated format', () => {
		expect(AUTO_GENERATED_NAME_RE.test('crazyPinkLizard')).toBe(false);
		expect(AUTO_GENERATED_NAME_RE.test('CrazyLizard')).toBe(false);
		expect(AUTO_GENERATED_NAME_RE.test('CustomDisplayName')).toBe(false);
	});
});
