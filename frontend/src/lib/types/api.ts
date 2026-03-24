export type ProviderId = 'spotify';

export interface AuthResponse {
	success: boolean;
	message: string;
	token?: string | null;
}

export interface RoomResponse {
	success: boolean;
	message: string;
	room_id?: string | null;
	join_code?: string | null;
}

export interface CreateRoomRequest {
	name: string;
	user_id: string;
	supported_provider_id: ProviderId;
}

export interface RoomRequest {
	room_id: string;
	user_id: string;
}

export interface DeleteRoomRequest {
	room_id: string;
	user_id: string;
}

export interface PlaybackRequest {
	user_id: string;
	action: 'pause' | 'resume' | 'stop';
}

export interface VoteRequest {
	user_id: string;
	vote_type: 'upvote' | 'downvote' | 'neutral';
}

export interface TrackDto {
	trackId: string;
	providerTrackId: string;
	title: string;
	artist: string;
	album: string;
	duration: number;
	coverUrl: string;
	deepLink: string;
}

export interface QueueFeedbackDto {
	userId: string;
	votedAt: string;
	type: 'upvote' | 'downvote';
}

export interface QueueEntryDto {
	queueEntryId: string;
	track: TrackDto;
	addedBy: {
		userId: string;
		displayName: string;
	};
	queuedAt: string;
	position: number;
	status: string;
	voteScore: number;
	orderRank: number;
	feedback: QueueFeedbackDto[];
}

export interface RoomStateDto {
	room: {
		roomId: string;
		joinCode: string;
		name: string;
		status: string;
		createdAt: string;
		supportedProviderId?: string;
	};
	host: {
		userId: string;
		displayName: string;
		createdAt: string;
	};
	users: Array<{
		user: {
			userId: string;
			displayName: string;
			createdAt: string;
		};
		membership: {
			joinedAt: string;
			leftAt: string | null;
			membershipStatus: string;
		};
	}>;
	queue: QueueEntryDto[];
	playback?: {
		state: 'playing' | 'paused' | 'stopped';
		currentQueueEntryId: string | null;
		updatedAt: string;
		positionMs: number;
	};
	lastEvent?: {
		type: string;
		at: string;
	};
}

export interface SearchResponseDto {
	provider: string;
	query: string;
	tracks: TrackDto[];
}
