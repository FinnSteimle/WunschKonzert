export type ProviderId = 'spotify' | 'apple-music';

export interface AppleMusicProfileDto {
	linked: boolean;
	storefront: string | null;
	display_name: string | null;
	needs_relink: boolean;
}

export interface AppleMusicLinkRequest {
	user_id: string;
	music_user_token: string;
	display_name: string;
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
	display_name: string;
	supported_provider_id: ProviderId;
}

export interface RoomRequest {
	join_code: string;
	user_id: string;
	display_name: string;
}

export interface LeaveRoomRequest {
	room_id: string;
	user_id: string;
}

export interface DeleteRoomRequest {
	room_id: string;
	user_id: string;
}

export interface RoomAvailabilityRequest {
	join_codes: string[];
}

export interface RoomAvailabilityResponse {
	available_join_codes: string[];
	unavailable_join_codes: string[];
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
	type: 'upvote' | 'downvote' | 'skip' | 'replay';
}

export interface QueueEntryDto {
	queueEntryId: string;
	track: TrackDto;
	addedBy: {
		userId: string;
		displayName: string;
	};
	queuedAt: string;
	playedAt?: string | null;
	position: number;
	status: string;
	voteScore: number;
	orderRank: number;
	feedback: QueueFeedbackDto[];
}

/** Present while the room may collect votes to replay the last-completed track (backend contract). */
export type ReplayVoteStatus = 'open' | 'met' | 'expired';

export interface ReplayVoteStateDto {
	targetQueueEntryId: string;
	track: TrackDto;
	voteCount: number;
	voterUserIds: string[];
	activeUserCount: number;
	closesAt: string;
	status: ReplayVoteStatus;
}

/** Pending host hand-off invite (in-memory on server, included in room state). */
export interface HostTransferDto {
	transferId: string;
	fromUserId: string;
	toUserId: string;
	createdAt: string;
}

export interface SystemMessageDto {
	id: string;
	text: string;
	at: string;
}

export interface LastActivityDto {
	type: string;
	userId: string;
	username: string;
	at: string;
	queueEntryId?: string;
}

/** One finished play from server `history` (playback_history). */
export interface PlaybackHistoryEntryDto {
	historyId: number;
	playedAt: string;
	track: TrackDto;
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
	/** Recent completed plays (newest first from API); optional for older clients/tests. */
	history?: PlaybackHistoryEntryDto[];
	playback?: {
		state: 'playing' | 'paused' | 'stopped';
		currentQueueEntryId: string | null;
		updatedAt: string;
		positionMs: number;
	};
	replayVote?: ReplayVoteStateDto | null;
	transfer?: HostTransferDto | null;
	systemMessages?: SystemMessageDto[];
	lastEvent?: {
		type: string;
		at: string;
	};
	lastActivity?: LastActivityDto;
}

export interface VoteRequest {
	user_id: string;
	vote_type: 'upvote' | 'downvote' | 'neutral' | 'skip' | 'replay';
}

export interface SearchResponseDto {
	provider: string;
	query: string;
	tracks: TrackDto[];
}
