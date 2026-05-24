/** True when the browser blocked programmatic audio (autoplay policy). */
export function isAutoplayBlockedError(err: unknown): boolean {
	if (!(err instanceof Error)) return false;
	const message = err.message.toLowerCase();
	return (
		err.name === 'NotAllowedError' ||
		message.includes("didn't interact") ||
		message.includes('user gesture') ||
		message.includes('autoplay')
	);
}
