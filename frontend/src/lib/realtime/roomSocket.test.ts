import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RoomSocketClient } from './roomSocket';

vi.mock('$lib/api/client', async (importOriginal) => {
	const actual = await importOriginal<typeof import('$lib/api/client')>();
	return {
		...actual,
		getWsBaseUrl: () => 'ws://localhost:8000'
	};
});

class MockWebSocket {
	static readonly OPEN = 1;
	static readonly CLOSED = 3;
	static readonly CONNECTING = 0;

	readyState = MockWebSocket.CONNECTING;
	url: string;

	onopen: ((ev: Event) => void) | null = null;
	onclose: ((ev: CloseEvent) => void) | null = null;
	onmessage: ((ev: MessageEvent) => void) | null = null;
	onerror: ((ev: Event) => void) | null = null;

	sent: string[] = [];

	constructor(url: string) {
		this.url = url;
	}

	send(data: string) {
		this.sent.push(data);
	}

	close() {
		this.readyState = MockWebSocket.CLOSED;
		this.onclose?.(new CloseEvent('close'));
	}

	simulateOpen() {
		this.readyState = MockWebSocket.OPEN;
		this.onopen?.(new Event('open'));
	}

	simulateMessage(data: unknown) {
		this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }));
	}

	simulateInvalidMessage() {
		this.onmessage?.(new MessageEvent('message', { data: '{bad json' }));
	}

	simulateError() {
		this.onerror?.(new Event('error'));
	}
}

let createdSockets: MockWebSocket[] = [];

describe('RoomSocketClient', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		createdSockets = [];
		vi.stubGlobal(
			'WebSocket',
			class extends MockWebSocket {
				constructor(url: string) {
					super(url);
					createdSockets.push(this);
				}
			}
		);
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('connects to the correct WebSocket URL', () => {
		const handlers = { onState: vi.fn() };
		const client = new RoomSocketClient('my-room', handlers);
		client.connect();

		expect(createdSockets).toHaveLength(1);
		expect(createdSockets[0].url).toBe('ws://localhost:8000/ws/my-room');

		client.disconnect();
	});

	it('encodes room id in the URL', () => {
		const handlers = { onState: vi.fn() };
		const client = new RoomSocketClient('room with spaces', handlers);
		client.connect();

		expect(createdSockets[0].url).toBe('ws://localhost:8000/ws/room%20with%20spaces');

		client.disconnect();
	});

	it('calls onConnectionChange(true) on open', () => {
		const onConnectionChange = vi.fn();
		const client = new RoomSocketClient('room-1', { onState: vi.fn(), onConnectionChange });
		client.connect();

		createdSockets[0].simulateOpen();

		expect(onConnectionChange).toHaveBeenCalledWith(true);

		client.disconnect();
	});

	it('calls onState with parsed payload on message', () => {
		const onState = vi.fn();
		const client = new RoomSocketClient('room-1', { onState });
		client.connect();
		createdSockets[0].simulateOpen();

		const payload = { room: { roomId: 'room-1' } };
		createdSockets[0].simulateMessage(payload);

		expect(onState).toHaveBeenCalledWith(payload);

		client.disconnect();
	});

	it('calls onError when message cannot be parsed', () => {
		const onError = vi.fn();
		const client = new RoomSocketClient('room-1', { onState: vi.fn(), onError });
		client.connect();
		createdSockets[0].simulateOpen();

		createdSockets[0].simulateInvalidMessage();

		expect(onError).toHaveBeenCalledWith('Could not parse room update from server');

		client.disconnect();
	});

	it('calls onError on WebSocket error', () => {
		const onError = vi.fn();
		const client = new RoomSocketClient('room-1', { onState: vi.fn(), onError });
		client.connect();

		createdSockets[0].simulateError();

		expect(onError).toHaveBeenCalledWith('WebSocket connection error');

		client.disconnect();
	});

	it('calls onConnectionChange(false) on close', () => {
		const onConnectionChange = vi.fn();
		const client = new RoomSocketClient('room-1', { onState: vi.fn(), onConnectionChange });
		client.connect();
		createdSockets[0].simulateOpen();

		createdSockets[0].close();

		expect(onConnectionChange).toHaveBeenCalledWith(false);

		client.disconnect();
	});

	it('attempts reconnection after close', () => {
		const client = new RoomSocketClient('room-1', { onState: vi.fn() });
		client.connect();
		expect(createdSockets).toHaveLength(1);

		createdSockets[0].close();
		expect(createdSockets).toHaveLength(1);

		vi.advanceTimersByTime(1500);
		expect(createdSockets).toHaveLength(2);

		client.disconnect();
	});

	it('does not reconnect after disconnect', () => {
		const client = new RoomSocketClient('room-1', { onState: vi.fn() });
		client.connect();

		client.disconnect();
		vi.advanceTimersByTime(5000);

		expect(createdSockets).toHaveLength(1);
	});

	it('does not create a second socket if already open', () => {
		const client = new RoomSocketClient('room-1', { onState: vi.fn() });
		client.connect();
		createdSockets[0].simulateOpen();

		client.connect();

		expect(createdSockets).toHaveLength(1);

		client.disconnect();
	});

	it('does not connect if disposed', () => {
		const client = new RoomSocketClient('room-1', { onState: vi.fn() });
		client.disconnect();
		client.connect();

		expect(createdSockets).toHaveLength(0);
	});

	describe('send', () => {
		it('sends JSON payload when socket is open', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			const result = client.send({ type: 'test' });

			expect(result).toBe(true);
			expect(createdSockets[0].sent).toEqual([JSON.stringify({ type: 'test' })]);

			client.disconnect();
		});

		it('returns false when socket is not open', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();

			expect(client.send({ type: 'test' })).toBe(false);

			client.disconnect();
		});

		it('returns false when no socket exists', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			expect(client.send({ type: 'test' })).toBe(false);
		});
	});

	describe('isConnected', () => {
		it('returns true when socket is open', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			expect(client.isConnected()).toBe(true);

			client.disconnect();
		});

		it('returns false when socket is not open', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();

			expect(client.isConnected()).toBe(false);

			client.disconnect();
		});

		it('returns false when not connected', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			expect(client.isConnected()).toBe(false);
		});
	});

	describe('sendVote', () => {
		it('sends vote payload with correct shape', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			client.sendVote('q1', 'user-1', 'upvote');

			expect(JSON.parse(createdSockets[0].sent[0])).toEqual({
				type: 'vote',
				queue_entry_id: 'q1',
				user_id: 'user-1',
				vote_type: 'upvote'
			});

			client.disconnect();
		});
	});

	describe('addToQueue', () => {
		it('sends addqueue payload with track and user', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			const track = {
				trackId: 't1',
				providerTrackId: 'spotify:t1',
				title: 'Song',
				artist: 'Artist',
				album: 'Album',
				duration: 200_000,
				coverUrl: '',
				deepLink: ''
			};
			client.addToQueue(track, 'user-1');

			expect(JSON.parse(createdSockets[0].sent[0])).toEqual({
				type: 'addqueue',
				track,
				user_id: 'user-1'
			});

			client.disconnect();
		});
	});

	describe('setPlayback', () => {
		it('sends pause payload', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			client.setPlayback('user-1', 'pause');

			expect(JSON.parse(createdSockets[0].sent[0])).toEqual({
				type: 'playback',
				user_id: 'user-1',
				action: 'pause'
			});

			client.disconnect();
		});

		it('sends resume payload', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			client.setPlayback('user-1', 'resume');

			expect(JSON.parse(createdSockets[0].sent[0])).toEqual({
				type: 'playback',
				user_id: 'user-1',
				action: 'resume'
			});

			client.disconnect();
		});
	});

	describe('renameDisplayName', () => {
		it('sends rename payload', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			client.renameDisplayName('user-1', 'Bob');

			expect(JSON.parse(createdSockets[0].sent[0])).toEqual({
				type: 'rename',
				user_id: 'user-1',
				display_name: 'Bob'
			});

			client.disconnect();
		});
	});

	describe('sendReplayVote', () => {
		it('sends replay_vote for vote', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			client.sendReplayVote('user-1', 'vote');

			expect(JSON.parse(createdSockets[0].sent[0])).toEqual({
				type: 'replay_vote',
				user_id: 'user-1',
				action: 'vote'
			});

			client.disconnect();
		});

		it('sends replay_vote for retract', () => {
			const client = new RoomSocketClient('room-1', { onState: vi.fn() });
			client.connect();
			createdSockets[0].simulateOpen();

			client.sendReplayVote('user-1', 'retract');

			expect(JSON.parse(createdSockets[0].sent[0])).toEqual({
				type: 'replay_vote',
				user_id: 'user-1',
				action: 'retract'
			});

			client.disconnect();
		});
	});
});
