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


class ModelComparisonRequest(BaseModel):
    fen: str
    candidate_moves: Optional[List[str]] = None
