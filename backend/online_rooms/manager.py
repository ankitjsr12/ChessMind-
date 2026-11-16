"""Thread-safe in-memory Room Manager for Online 1v1 Chess.

IMPORTANT ARCHITECTURAL NOTE ON STATE PERSISTENCE:
In-memory rooms managed by this class are temporary and held in process RAM.
Backend restarts, server crashes, or container recreation will reset active rooms.
The manager is designed to support future database hydration via
`hydrate_room_from_db()` when durable reconnects are introduced in subsequent phases.
"""

from __future__ import annotations

import logging
import secrets
import string
import threading
import time
from typing import Dict, List, Optional, Tuple

from backend.online_rooms.models import (
    ColorPreference,
    OnlineRoom,
    PlayerConnectionState,
    PlayerSlot,
    RoomStatus,
)

logger = logging.getLogger(__name__)


class RoomManager:
    """Thread-safe manager for active online chess rooms.

    Handles room creation, joining, code uniqueness, player mapping, and idle cleanup.
    """

    # Unambiguous character set (excludes 0, O, 1, I to prevent human transcription errors)
    CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    CODE_LENGTH = 6

    def __init__(self) -> None:
        self._rooms: Dict[str, OnlineRoom] = {}
        self._user_to_room: Dict[str, str] = {}
        self._lock: threading.RLock = threading.RLock()

    def generate_unique_code(self) -> str:
        """Generate a cryptographically secure, unique 6-character room code."""
        with self._lock:
            for _ in range(50):
                code = "".join(secrets.choice(self.CODE_ALPHABET) for _ in range(self.CODE_LENGTH))
                if code not in self._rooms:
                    return code
            raise RuntimeError("Exhausted retries generating a unique room code.")

    def create_room(
        self,
        creator_user_id: str,
        creator_username: str,
        time_control_seconds: int = 600,
        increment_seconds: int = 0,
        is_private: bool = True,
        color_preference: ColorPreference = ColorPreference.RANDOM,
    ) -> OnlineRoom:
        """Create a new online room and seat the creator.

        Args:
            creator_user_id: Unique identifier for the creating user.
            creator_username: Display name of the creating user.
            time_control_seconds: Clock time per player in seconds (e.g. 180, 300, 600).
            increment_seconds: Time added per move in seconds.
            is_private: If True, room is hidden from public matchmaking.
            color_preference: Desired color (WHITE, BLACK, RANDOM).

        Returns:
            The created OnlineRoom instance.
        """
        with self._lock:
            # Generate code and create instance
            code = self.generate_unique_code()
            room = OnlineRoom(
                room_code=code,
                creator_user_id=creator_user_id,
                creator_username=creator_username,
                time_control_seconds=time_control_seconds,
                increment_seconds=increment_seconds,
                is_private=is_private,
                color_preference=color_preference,
            )

            self._rooms[code] = room
            self._user_to_room[creator_user_id] = code
            logger.info("Created room %s by user %s (private=%s)", code, creator_user_id, is_private)
            return room

    def get_room(self, room_code: str) -> Optional[OnlineRoom]:
        """Look up an active room by code (case-insensitive)."""
        clean_code = room_code.upper().strip()
        with self._lock:
            return self._rooms.get(clean_code)

    def join_room(
        self,
        room_code: str,
        user_id: str,
        username: str,
    ) -> Tuple[OnlineRoom, PlayerSlot]:
        """Seat a player in an existing room or reconnect them.

        Args:
            room_code: Code of the room to join.
            user_id: Unique identifier for the joining user.
            username: Display name of the joining user.

        Returns:
            Tuple of (OnlineRoom, assigned PlayerSlot).

        Raises:
            KeyError: If room code does not exist.
            ValueError: If room is full and user is not an existing participant.
        """
        clean_code = room_code.upper().strip()
        with self._lock:
            room = self._rooms.get(clean_code)
            if not room:
                raise KeyError(f"Room '{clean_code}' not found.")

            slot = room.add_player(user_id=user_id, username=username)
            self._user_to_room[user_id] = clean_code
            logger.info("User %s joined room %s as %s", user_id, clean_code, slot.assigned_color)
            return room, slot

    def get_user_active_room(self, user_id: str) -> Optional[OnlineRoom]:
        """Retrieve the active room currently associated with a user."""
        with self._lock:
            code = self._user_to_room.get(user_id)
            if code and code in self._rooms:
                return self._rooms[code]
            return None

    def set_player_connection_state(
        self,
        room_code: str,
        user_id: str,
        state: PlayerConnectionState,
    ) -> Optional[OnlineRoom]:
        """Update a player's real-time connection state."""
        clean_code = room_code.upper().strip()
        with self._lock:
            room = self._rooms.get(clean_code)
            if not room:
                return None

            player = room.get_player_by_id(user_id)
            if player:
                player.connection_state = state
                now = time.time()
                player.last_heartbeat_at = now
                if state == PlayerConnectionState.DISCONNECTED:
                    player.disconnected_at = now
                elif state == PlayerConnectionState.CONNECTED:
                    player.disconnected_at = None
            return room

    def leave_room(self, room_code: str, user_id: str) -> Optional[OnlineRoom]:
        """Mark a player as having left the room."""
        clean_code = room_code.upper().strip()
        with self._lock:
            room = self._rooms.get(clean_code)
            if not room:
                return None

            player = room.get_player_by_id(user_id)
            if player:
                player.connection_state = PlayerConnectionState.LEFT
                player.disconnected_at = time.time()

            # Clean user mapping
            if self._user_to_room.get(user_id) == clean_code:
                del self._user_to_room[user_id]

            # If room was still waiting and creator left, mark aborted
            if room.status == RoomStatus.WAITING and user_id == room.creator_user_id:
                room.status = RoomStatus.ABORTED

            return room

    def remove_room(self, room_code: str) -> bool:
        """Remove a room from active in-memory management."""
        clean_code = room_code.upper().strip()
        with self._lock:
            room = self._rooms.pop(clean_code, None)
            if room:
                # Clear user mappings
                if room.white_player and self._user_to_room.get(room.white_player.user_id) == clean_code:
                    del self._user_to_room[room.white_player.user_id]
                if room.black_player and self._user_to_room.get(room.black_player.user_id) == clean_code:
                    del self._user_to_room[room.black_player.user_id]
                return True
            return False

    def list_public_waiting_rooms(self) -> List[OnlineRoom]:
        """Return all non-private rooms that are currently waiting for an opponent."""
        with self._lock:
            return [
                room
                for room in self._rooms.values()
                if not room.is_private and room.status == RoomStatus.WAITING
            ]

    def cleanup_idle_rooms(self, max_idle_seconds: float = 7200.0) -> int:
        """Evict stale or completed rooms that have had no activity for max_idle_seconds."""
        now = time.time()
        evicted = 0
        with self._lock:
            stale_codes = []
            for code, room in self._rooms.items():
                last_activity = room.last_move_at or room.created_at
                is_stale = (now - last_activity) > max_idle_seconds
                is_done_and_old = (
                    room.status in (RoomStatus.COMPLETED, RoomStatus.ABORTED)
                    and (now - last_activity) > 300.0  # Retain finished rooms for 5 mins
                )
                if is_stale or is_done_and_old:
                    stale_codes.append(code)

            for code in stale_codes:
                self.remove_room(code)
                evicted += 1

        return evicted

    def active_rooms_count(self) -> int:
        """Return total active rooms currently managed in memory."""
        with self._lock:
            return len(self._rooms)


# Global singleton instance for application use
room_manager = RoomManager()

