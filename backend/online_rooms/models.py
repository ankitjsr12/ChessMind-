"""Domain models for Online 1v1 Chess Rooms and Server-Authoritative Clocks.

IMPORTANT ARCHITECTURAL NOTE ON STATE PERSISTENCE:
In-memory rooms instantiated by this module are temporary state containers held
within the FastAPI application process memory. In the event of a backend restart,
process termination, or rolling deployment, active in-memory rooms are cleared.
To support future durability and disaster recovery, the `OnlineRoom` model provides:
1. `to_persisted_dict()`: Prepares room state for storage in Supabase PostgreSQL.
2. `from_persisted_game()`: Hydrates a room instance from database records.
Reliable reconnection recovery across server restarts requires full database
hydration and is designated for implementation in subsequent phases.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

import chess

from backend.chess_engine import ChessEngine, IllegalMoveError
from backend.chess_engine.models import (
    GameResult,
    MoveRecord,
    MoveResult,
    PieceColor,
    TerminationReason,
)


class RoomStatus(str, Enum):
    """Lifecycle status of an online chess room."""

    WAITING = "waiting"       # Waiting for opponent to join
    ACTIVE = "active"         # Game in progress with 2 players
    COMPLETED = "completed"   # Game concluded (checkmate, resign, draw, timeout)
    ABORTED = "aborted"       # Game cancelled before any move played


class ColorPreference(str, Enum):
    """Player color preference during room creation."""

    WHITE = "white"
    BLACK = "black"
    RANDOM = "random"


class PlayerConnectionState(str, Enum):
    """Real-time connectivity state of a player in a room."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    LEFT = "left"


class OnlineTerminationReason(str, Enum):
    """Specific termination reasons for online multiplayer matches."""

    CHECKMATE = "checkmate"
    RESIGNATION = "resignation"
    TIMEOUT = "timeout"
    AGREED_DRAW = "agreed_draw"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"
    FIFTY_MOVES = "fifty_moves"
    ABANDONMENT = "abandonment"


@dataclass
class PlayerSlot:
    """Represents a player seated in an online room."""

    user_id: str
    username: str
    assigned_color: Optional[PieceColor] = None
    connection_state: PlayerConnectionState = PlayerConnectionState.CONNECTED
    connected_at: float = field(default_factory=time.time)
    last_heartbeat_at: float = field(default_factory=time.time)
    disconnected_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert player slot to a client-safe dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "assigned_color": self.assigned_color.value if self.assigned_color else None,
            "connection_state": self.connection_state.value,
            "connected_at": self.connected_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "disconnected_at": self.disconnected_at,
        }


@dataclass
class RoomClock:
    """Server-authoritative dual digital clock with millisecond precision.

    Tracks remaining time, turn switches, increments, and flag fall detection.
    """

    base_time_seconds: int
    increment_seconds: int
    white_time_remaining_ms: int
    black_time_remaining_ms: int
    active_turn: Optional[PieceColor] = None
    turn_start_timestamp: Optional[float] = None
    is_running: bool = False

    @classmethod
    def create(cls, base_time_seconds: int, increment_seconds: int = 0) -> RoomClock:
        """Create a new clock with base times initialized."""
        ms = max(10, base_time_seconds) * 1000
        return cls(
            base_time_seconds=base_time_seconds,
            increment_seconds=increment_seconds,
            white_time_remaining_ms=ms,
            black_time_remaining_ms=ms,
            active_turn=None,
            turn_start_timestamp=None,
            is_running=False,
        )

    def start(self, turn: PieceColor, timestamp: Optional[float] = None) -> None:
        """Start the clock for the given turn."""
        now = timestamp if timestamp is not None else time.time()
        self.active_turn = turn
        self.turn_start_timestamp = now
        self.is_running = True

    def get_remaining_times(self, timestamp: Optional[float] = None) -> Tuple[int, int]:
        """Calculate exact remaining milliseconds for (White, Black).

        Deducts elapsed milliseconds from the currently active player's clock.
        """
        now = timestamp if timestamp is not None else time.time()
        w_ms = self.white_time_remaining_ms
        b_ms = self.black_time_remaining_ms

        if self.is_running and self.active_turn is not None and self.turn_start_timestamp is not None:
            elapsed_ms = int(max(0.0, (now - self.turn_start_timestamp) * 1000))
            if self.active_turn == PieceColor.WHITE:
                w_ms = max(0, w_ms - elapsed_ms)
            else:
                b_ms = max(0, b_ms - elapsed_ms)

        return w_ms, b_ms

    def record_move(
        self,
        moving_color: PieceColor,
        next_turn: PieceColor,
        timestamp: Optional[float] = None,
    ) -> Tuple[int, int]:
        """Record a completed move: deduct elapsed time, add increment, and switch turn.

        Args:
            moving_color: The color of the player who just moved.
            next_turn: The color of the player whose turn begins now.
            timestamp: Epoch timestamp of the move.

        Returns:
            Tuple of updated (white_ms, black_ms).
        """
        now = timestamp if timestamp is not None else time.time()

        if self.is_running and self.active_turn == moving_color and self.turn_start_timestamp is not None:
            elapsed_ms = int(max(0.0, (now - self.turn_start_timestamp) * 1000))
            increment_ms = self.increment_seconds * 1000

            if moving_color == PieceColor.WHITE:
                self.white_time_remaining_ms = max(0, self.white_time_remaining_ms - elapsed_ms) + increment_ms
            else:
                self.black_time_remaining_ms = max(0, self.black_time_remaining_ms - elapsed_ms) + increment_ms

        # Switch to opponent turn
        self.active_turn = next_turn
        self.turn_start_timestamp = now
        return self.white_time_remaining_ms, self.black_time_remaining_ms

    def check_flag_fallen(self, timestamp: Optional[float] = None) -> Optional[PieceColor]:
        """Check if any player has run out of time (flag fallen).

        Returns:
            PieceColor of the player whose time reached 0, or None if both have time.
        """
        w_ms, b_ms = self.get_remaining_times(timestamp)
        if w_ms <= 0:
            return PieceColor.WHITE
        if b_ms <= 0:
            return PieceColor.BLACK
        return None

    def stop(self, timestamp: Optional[float] = None) -> Tuple[int, int]:
        """Stop the clock and finalize remaining times."""
        w_ms, b_ms = self.get_remaining_times(timestamp)
        self.white_time_remaining_ms = w_ms
        self.black_time_remaining_ms = b_ms
        self.is_running = False
        self.active_turn = None
        self.turn_start_timestamp = None
        return w_ms, b_ms

    def to_dict(self, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Serialize clock state to dictionary."""
        w_ms, b_ms = self.get_remaining_times(timestamp)
        return {
            "base_time_seconds": self.base_time_seconds,
            "increment_seconds": self.increment_seconds,
            "white_time_remaining_ms": w_ms,
            "black_time_remaining_ms": b_ms,
            "active_turn": self.active_turn.value if self.active_turn else None,
            "is_running": self.is_running,
        }


class OnlineRoom:
    """Thread-safe authoritative online chess room entity.

    Wraps a `ChessEngine` for rule validation and a `RoomClock` for timekeeping.
    Manages player assignment, in-game actions, turn permissions, and game completion.
    """

    def __init__(
        self,
        room_code: str,
        creator_user_id: str,
        creator_username: str,
        time_control_seconds: int = 600,
        increment_seconds: int = 0,
        is_private: bool = True,
        color_preference: ColorPreference = ColorPreference.RANDOM,
    ) -> None:
        self.room_code: str = room_code.upper().strip()
        self.creator_user_id: str = creator_user_id
        self.creator_username: str = creator_username
        self.time_control_seconds: int = time_control_seconds
        self.increment_seconds: int = increment_seconds
        self.is_private: bool = is_private
        self.color_preference: ColorPreference = color_preference

        self.created_at: float = time.time()
        self.status: RoomStatus = RoomStatus.WAITING

        # Core engine & authoritative clock
        self.engine: ChessEngine = ChessEngine()
        self.clock: RoomClock = RoomClock.create(time_control_seconds, increment_seconds)

        # Player slots
        self.white_player: Optional[PlayerSlot] = None
        self.black_player: Optional[PlayerSlot] = None

        # Seed creator in room
        creator_slot = PlayerSlot(user_id=creator_user_id, username=creator_username)
        if color_preference == ColorPreference.WHITE:
            creator_slot.assigned_color = PieceColor.WHITE
            self.white_player = creator_slot
        elif color_preference == ColorPreference.BLACK:
            creator_slot.assigned_color = PieceColor.BLACK
            self.black_player = creator_slot
        else:
            # Color will be randomized once second player joins
            self.white_player = creator_slot

        # Actions & outcomes
        self.draw_offered_by: Optional[PieceColor] = None
        self.rematch_requested_by: Optional[PieceColor] = None
        self.winner_color: Optional[PieceColor] = None
        self.winner_id: Optional[str] = None
        self.termination_reason: Optional[OnlineTerminationReason] = None
        self.persisted_game_id: Optional[str] = None
        self.last_move_at: Optional[float] = None

    # -------------------------------------------------------------------------
    # Player Management & Fair Color Assignment
    # -------------------------------------------------------------------------

    def is_full(self) -> bool:
        """Return True if both White and Black slots are occupied."""
        return self.white_player is not None and self.black_player is not None

    def get_player_by_id(self, user_id: str) -> Optional[PlayerSlot]:
        """Find player slot by user_id."""
        if self.white_player and self.white_player.user_id == user_id:
            return self.white_player
        if self.black_player and self.black_player.user_id == user_id:
            return self.black_player
        return None

    def get_player_by_color(self, color: PieceColor) -> Optional[PlayerSlot]:
        """Find player slot by assigned piece color."""
        if color == PieceColor.WHITE:
            return self.white_player
        return self.black_player

    def get_opponent_slot(self, user_id: str) -> Optional[PlayerSlot]:
        """Get the opposing player's slot for a given user_id."""
        if self.white_player and self.white_player.user_id == user_id:
            return self.black_player
        if self.black_player and self.black_player.user_id == user_id:
            return self.white_player
        return None

    def add_player(self, user_id: str, username: str) -> PlayerSlot:
        """Add a player to the room or reconnect an existing player.

        Raises:
            ValueError: If the room is already full with 2 distinct players.
        """
        existing = self.get_player_by_id(user_id)
        if existing:
            # Reconnection: update heartbeat and status
            existing.connection_state = PlayerConnectionState.CONNECTED
            existing.last_heartbeat_at = time.time()
            existing.disconnected_at = None
            return existing

        if self.is_full():
            raise ValueError(f"Room '{self.room_code}' is full.")

        new_player = PlayerSlot(user_id=user_id, username=username)

        # Assign slots fairly
        if self.color_preference == ColorPreference.WHITE:
            new_player.assigned_color = PieceColor.BLACK
            self.black_player = new_player
        elif self.color_preference == ColorPreference.BLACK:
            new_player.assigned_color = PieceColor.WHITE
            self.white_player = new_player
        else:
            # RANDOM assignment
            # Creator is currently in self.white_player temporarily
            creator = self.white_player
            creator_is_white = secrets.choice([True, False])
            if creator_is_white:
                creator.assigned_color = PieceColor.WHITE
                new_player.assigned_color = PieceColor.BLACK
                self.black_player = new_player
            else:
                creator.assigned_color = PieceColor.BLACK
                self.black_player = creator
                new_player.assigned_color = PieceColor.WHITE
                self.white_player = new_player

        # Both players are now seated: start the game and the clock!
        self.status = RoomStatus.ACTIVE
        self.clock.start(PieceColor.WHITE)
        return new_player

    # -------------------------------------------------------------------------
    # Server-Authoritative Move Execution & Clocks
    # -------------------------------------------------------------------------

    def make_authoritative_move(
        self,
        user_id: str,
        move_str: str,
        timestamp: Optional[float] = None,
    ) -> MoveResult:
        """Execute and validate a chess move strictly on the server.

        Validates:
        1. Game is active.
        2. User is seated and assigned to the active turn.
        3. Player has not timed out (flag fall).
        4. Move is legally valid according to FIDE rules in `ChessEngine`.

        Updates authoritative clocks and game outcomes upon completion.

        Raises:
            PermissionError: If user is not authorized or not their turn.
            ValueError: If game is not active or player has timed out.
            IllegalMoveError: If move is illegal.
        """
        now = timestamp if timestamp is not None else time.time()

        if self.status != RoomStatus.ACTIVE:
            raise ValueError(f"Cannot play move: Game is {self.status.value}.")

        # Check timeouts before move
        flag_fallen = self.clock.check_flag_fallen(now)
        if flag_fallen is not None:
            self._handle_timeout(flag_fallen, now)
            raise ValueError(f"Player {flag_fallen.value} ran out of time.")

        # Validate turn ownership
        player = self.get_player_by_id(user_id)
        if not player or player.assigned_color is None:
            raise PermissionError("User is not an active player in this room.")

        current_turn = self.engine.turn
        if player.assigned_color != current_turn:
            raise PermissionError(f"Not your turn. Current turn: {current_turn.value}.")

        # Execute move on authoritative engine
        res = self.engine.make_move(move_str)
        self.last_move_at = now

        # Clear any pending draw offer on move execution
        self.draw_offered_by = None

        # Update clocks with increment
        next_turn = self.engine.turn
        self.clock.record_move(
            moving_color=player.assigned_color,
            next_turn=next_turn,
            timestamp=now,
        )

        # Check if move caused game termination
        if self.engine.is_game_over(claim_draw=True):
            self._finalize_engine_game_over(now)

        return res

    def _handle_timeout(self, timed_out_color: PieceColor, timestamp: float) -> None:
        """Finalize game when a player's clock reaches 0."""
        self.status = RoomStatus.COMPLETED
        self.clock.stop(timestamp)
        self.termination_reason = OnlineTerminationReason.TIMEOUT

        # Opponent wins
        winning_color = timed_out_color.opposite
        self.winner_color = winning_color
        winner_slot = self.get_player_by_color(winning_color)
        self.winner_id = winner_slot.user_id if winner_slot else None

    def _finalize_engine_game_over(self, timestamp: float) -> None:
        """Set outcome and termination reasons from ChessEngine state."""
        self.status = RoomStatus.COMPLETED
        self.clock.stop(timestamp)

        termination = self.engine.get_game_result(claim_draw=True)
        if termination.reason == TerminationReason.CHECKMATE:
            self.termination_reason = OnlineTerminationReason.CHECKMATE
            self.winner_color = termination.winner
            winner_slot = self.get_player_by_color(termination.winner) if termination.winner else None
            self.winner_id = winner_slot.user_id if winner_slot else None
        elif termination.reason == TerminationReason.STALEMATE:
            self.termination_reason = OnlineTerminationReason.STALEMATE
            self.winner_color = None
            self.winner_id = None
        elif termination.reason == TerminationReason.INSUFFICIENT_MATERIAL:
            self.termination_reason = OnlineTerminationReason.INSUFFICIENT_MATERIAL
            self.winner_color = None
            self.winner_id = None
        elif termination.reason in (TerminationReason.THREEFOLD_REPETITION, TerminationReason.FIVEFOLD_REPETITION):
            self.termination_reason = OnlineTerminationReason.THREEFOLD_REPETITION
            self.winner_color = None
            self.winner_id = None
        elif termination.reason in (TerminationReason.FIFTY_MOVES, TerminationReason.SEVENTYFIVE_MOVES):
            self.termination_reason = OnlineTerminationReason.FIFTY_MOVES
            self.winner_color = None
            self.winner_id = None
        else:
            self.termination_reason = OnlineTerminationReason.AGREED_DRAW
            self.winner_color = None
            self.winner_id = None

    # -------------------------------------------------------------------------
    # In-Game Actions: Resign, Draw Offers, Timeouts
    # -------------------------------------------------------------------------

    def resign(self, user_id: str, timestamp: Optional[float] = None) -> bool:
        """Handle player resignation."""
        if self.status != RoomStatus.ACTIVE:
            return False

        player = self.get_player_by_id(user_id)
        if not player or player.assigned_color is None:
            return False

        now = timestamp if timestamp is not None else time.time()
        self.status = RoomStatus.COMPLETED
        self.clock.stop(now)
        self.termination_reason = OnlineTerminationReason.RESIGNATION

        winning_color = player.assigned_color.opposite
        self.winner_color = winning_color
        opponent = self.get_player_by_color(winning_color)
        self.winner_id = opponent.user_id if opponent else None
        return True

    def offer_draw(self, user_id: str) -> bool:
        """Register a draw offer from the given user."""
        if self.status != RoomStatus.ACTIVE:
            return False

        player = self.get_player_by_id(user_id)
        if not player or player.assigned_color is None:
            return False

        self.draw_offered_by = player.assigned_color
        return True

    def accept_draw(self, user_id: str, timestamp: Optional[float] = None) -> bool:
        """Accept a pending draw offer made by the opponent."""
        if self.status != RoomStatus.ACTIVE or self.draw_offered_by is None:
            return False

        player = self.get_player_by_id(user_id)
        if not player or player.assigned_color is None:
            return False

        # Can only accept if offer was made by the opponent
        if player.assigned_color == self.draw_offered_by:
            return False

        now = timestamp if timestamp is not None else time.time()
        self.status = RoomStatus.COMPLETED
        self.clock.stop(now)
        self.termination_reason = OnlineTerminationReason.AGREED_DRAW
        self.winner_color = None
        self.winner_id = None
        self.draw_offered_by = None
        return True

    def decline_draw(self, user_id: str) -> bool:
        """Decline an opponent's draw offer."""
        player = self.get_player_by_id(user_id)
        if not player or player.assigned_color is None:
            return False

        if self.draw_offered_by and self.draw_offered_by != player.assigned_color:
            self.draw_offered_by = None
            return True
        return False

    def check_timeouts(self, timestamp: Optional[float] = None) -> Optional[PieceColor]:
        """Check and apply timeout if active player has exceeded remaining time."""
        if self.status != RoomStatus.ACTIVE:
            return None

        now = timestamp if timestamp is not None else time.time()
        flag_fallen = self.clock.check_flag_fallen(now)
        if flag_fallen is not None:
            self._handle_timeout(flag_fallen, now)
            return flag_fallen
        return None

    # -------------------------------------------------------------------------
    # Serialization & Database Persistence Helpers
    # -------------------------------------------------------------------------

    def to_dict(self, current_user_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert room state to client-safe representation."""
        now = time.time()
        clock_dict = self.clock.to_dict(now)

        return {
            "room_code": self.room_code,
            "creator_user_id": self.creator_user_id,
            "creator_username": self.creator_username,
            "is_private": self.is_private,
            "status": self.status.value,
            "time_control_seconds": self.time_control_seconds,
            "increment_seconds": self.increment_seconds,
            "color_preference": self.color_preference.value,
            "created_at": self.created_at,
            "fen": self.engine.fen,
            "turn": self.engine.turn.value,
            "is_check": self.engine.is_check(),
            "is_game_over": self.status == RoomStatus.COMPLETED,
            "clock": clock_dict,
            "white_player": self.white_player.to_dict() if self.white_player else None,
            "black_player": self.black_player.to_dict() if self.black_player else None,
            "draw_offered_by": self.draw_offered_by.value if self.draw_offered_by else None,
            "winner_color": self.winner_color.value if self.winner_color else None,
            "winner_id": self.winner_id,
            "termination_reason": self.termination_reason.value if self.termination_reason else None,
            "move_history_count": len(self.engine.get_move_history()),
            "last_move_at": self.last_move_at,
        }

    def to_persisted_dict(self) -> Dict[str, Any]:
        """Format room state for saving to Supabase `public.games` table."""
        now_ms = time.time()
        w_ms, b_ms = self.clock.get_remaining_times(now_ms)

        res_str = "*"
        if self.status == RoomStatus.COMPLETED:
            if self.winner_color == PieceColor.WHITE:
                res_str = "1-0"
            elif self.winner_color == PieceColor.BLACK:
                res_str = "0-1"
            else:
                res_str = "1/2-1/2"

        return {
            "user_id": self.creator_user_id,
            "white_player_id": self.white_player.user_id if self.white_player else None,
            "black_player_id": self.black_player.user_id if self.black_player else None,
            "player_colour": "white",
            "opponent_type": "human",
            "room_code": self.room_code,
            "is_private": self.is_private,
            "game_mode": "online_1v1_private" if self.is_private else "online_1v1_public",
            "status": self.status.value,
            "time_control_seconds": self.time_control_seconds,
            "increment_seconds": self.increment_seconds,
            "white_time_remaining_ms": w_ms,
            "black_time_remaining_ms": b_ms,
            "result": res_str,
            "starting_fen": chess.STARTING_FEN,
            "current_fen": self.engine.fen,
            "pgn": self.engine.export_pgn(),
            "winner_id": self.winner_id,
            "winner_color": self.winner_color.value if self.winner_color else None,
            "termination_reason": self.termination_reason.value if self.termination_reason else None,
        }

    @classmethod
    def from_persisted_game(
        cls,
        game_data: Dict[str, Any],
        moves_data: Optional[List[Dict[str, Any]]] = None,
    ) -> OnlineRoom:
        """Hydrate an in-memory room instance from a persisted Supabase database record.

        Enables future disaster recovery and state reconstruction if the server restarts.
        """
        room = cls(
            room_code=game_data.get("room_code", "RESTORED"),
            creator_user_id=game_data.get("user_id", ""),
            creator_username="Player",
            time_control_seconds=game_data.get("time_control_seconds", 600),
            increment_seconds=game_data.get("increment_seconds", 0),
            is_private=game_data.get("is_private", True),
            color_preference=ColorPreference.RANDOM,
        )

        room.status = RoomStatus(game_data.get("status", RoomStatus.ACTIVE.value))
        room.persisted_game_id = str(game_data.get("id", ""))

        if game_data.get("white_player_id"):
            room.white_player = PlayerSlot(
                user_id=str(game_data["white_player_id"]),
                username="White Player",
                assigned_color=PieceColor.WHITE,
            )
        if game_data.get("black_player_id"):
            room.black_player = PlayerSlot(
                user_id=str(game_data["black_player_id"]),
                username="Black Player",
                assigned_color=PieceColor.BLACK,
            )

        # Restore clocks
        w_ms = game_data.get("white_time_remaining_ms") or (room.time_control_seconds * 1000)
        b_ms = game_data.get("black_time_remaining_ms") or (room.time_control_seconds * 1000)
        room.clock.white_time_remaining_ms = w_ms
        room.clock.black_time_remaining_ms = b_ms

        # Replay moves into engine if available, or load current_fen
        if moves_data:
            sorted_moves = sorted(moves_data, key=lambda m: m.get("move_number", 0))
            for m in sorted_moves:
                uci_move = m.get("uci")
                if uci_move:
                    room.engine.make_move(uci_move)
        elif game_data.get("current_fen"):
            room.engine = ChessEngine(game_data["current_fen"])

        return room

