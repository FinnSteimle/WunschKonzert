import type { RoomStateDto } from '$lib/types/api';
import type { TrackDto, VoteRequest } from '$lib/types/api';

const WS_BASE_URL = import.meta.env.PUBLIC_WS_URL ?? 'ws://localhost:8000';

interface RoomSocketHandlers {
	onState: (state: RoomStateDto) => void;
	onError?: (message: string) => void;
	onConnectionChange?: (connected: boolean) => void;
}

export class RoomSocketClient {
	private socket: WebSocket | null = null;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private disposed = false;
	private readonly roomId: string;
	private readonly handlers: RoomSocketHandlers;

	constructor(roomId: string, handlers: RoomSocketHandlers) {
		this.roomId = roomId;
		this.handlers = handlers;
	}

	connect() {
		if (this.disposed) return;
		if (this.socket && this.socket.readyState === WebSocket.OPEN) return;

		const url = `${WS_BASE_URL}/ws/${encodeURIComponent(this.roomId)}`;
		this.socket = new WebSocket(url);

		this.socket.onopen = () => {
			this.handlers.onConnectionChange?.(true);
		};

		this.socket.onmessage = (event) => {
			try {
				const payload = JSON.parse(event.data) as RoomStateDto;
				this.handlers.onState(payload);
			} catch {
				this.handlers.onError?.('Could not parse room update from server');
			}
		};

		this.socket.onerror = () => {
			this.handlers.onError?.('WebSocket connection error');
		};

		this.socket.onclose = () => {
			this.handlers.onConnectionChange?.(false);
			if (this.disposed) return;
			if (this.reconnectTimer) {
				clearTimeout(this.reconnectTimer);
			}
			this.reconnectTimer = setTimeout(() => this.connect(), 1500);
		};
	}

	send(payload: unknown) {
		if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
		this.socket.send(JSON.stringify(payload));
		return true;
	}

	isConnected() {
		return this.socket?.readyState === WebSocket.OPEN;
	}

	sendVote(queueEntryId: string, userId: string, voteType: VoteRequest['vote_type']) {
		return this.send({
			type: 'vote',
			queue_entry_id: queueEntryId,
			user_id: userId,
			vote_type: voteType
		});
	}

	addToQueue(track: TrackDto, userId: string) {
		return this.send({
			type: 'addqueue',
			track,
			user_id: userId
		});
	}

	removeQueueEntry(queueEntryId: string, userId: string) {
		return this.send({
			type: 'remove_queue_entry',
			queue_entry_id: queueEntryId,
			user_id: userId
		});
	}

	setPlayback(userId: string, action: 'pause' | 'resume', positionMs?: number) {
		const payload: Record<string, unknown> = {
			type: 'playback',
			user_id: userId,
			action
		};
		if (positionMs !== undefined) {
			payload.position_ms = Math.round(positionMs);
		}
		return this.send(payload);
	}

	renameDisplayName(userId: string, displayName: string) {
		return this.send({
			type: 'rename',
			user_id: userId,
			display_name: displayName
		});
	}

	disconnect() {
		this.disposed = true;
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
		}
		if (this.socket) {
			this.socket.close();
			this.socket = null;
		}
	}
}
