"""API schemas for FastAPI ChessMind AI service."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PositionRequest(BaseModel):
    fen: str = Field(..., description="Board FEN string")


class MoveRequest(BaseModel):
    fen: str
    move: str = Field(..., description="UCI or SAN move")


class PlayAIRequest(BaseModel):
    fen: str
    difficulty: str = Field(default="medium", description="easy | medium | master | neural")


class CandidatesRequest(BaseModel):
    fen: str
    candidate_moves: Optional[List[str]] = Field(default=None, description="Optional list of candidate moves")


class GameReviewRequest(BaseModel):
    moves: List[str] = Field(..., description="Sequence of moves in UCI or SAN")
    initial_fen: Optional[str] = Field(default=None, description="Starting FEN (defaults to standard starting position)")


class PGNReviewRequest(BaseModel):
    pgn: str = Field(..., description="Raw PGN string containing headers and movetext")


class LichessImportRequest(BaseModel):
    username: str = Field(..., description="Lichess username")
    max_games: int = Field(default=5, ge=1, le=20, description="Max games to fetch")


class ChessComImportRequest(BaseModel):
    username: str = Field(..., description="Chess.com username")
    max_games: int = Field(default=5, ge=1, le=20, description="Max games to fetch")


class OpeningExplorerRequest(BaseModel):
    fen: str = Field(..., description="Current board FEN")
    moves: Optional[List[str]] = Field(default=None, description="Moves played so far")


class ModelComparisonRequest(BaseModel):
    fen: str
    candidate_moves: Optional[List[str]] = None


# -----------------------------------------------------------------------------
# Online 1v1 Room Schemas
# -----------------------------------------------------------------------------

class CreateRoomRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Optional creator user ID (generated if omitted)")
    username: Optional[str] = Field(default="Player", description="Creator display name")
    time_control_seconds: int = Field(default=600, ge=30, le=7200, description="Base time per player in seconds")
    increment_seconds: int = Field(default=0, ge=0, le=60, description="Increment in seconds per move")
    is_private: bool = Field(default=True, description="Private room with invite code or public matchmaking")
    color_preference: str = Field(default="random", description="'white', 'black', or 'random'")


class JoinRoomRequest(BaseModel):
    room_code: str = Field(..., min_length=4, max_length=16, description="Alphanumeric room code")
    user_id: Optional[str] = Field(default=None, description="Optional joiner user ID (generated if omitted)")
    username: Optional[str] = Field(default="Player", description="Joiner display name")


class RoomMoveRequest(BaseModel):
    room_code: str = Field(..., description="Room code")
    user_id: str = Field(..., description="User ID of player executing move")
    move: str = Field(..., description="UCI or SAN move string")


class RoomActionRequest(BaseModel):
    room_code: str = Field(..., description="Room code")
    user_id: str = Field(..., description="User ID of player initiating action")
    action: str = Field(..., description="'resign', 'offer_draw', 'accept_draw', 'decline_draw', 'leave'")
