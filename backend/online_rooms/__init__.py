"""Online 1v1 Room Management & Server-Authoritative Clock Service for ChessMind AI."""

from backend.online_rooms.models import (
    ColorPreference,
    OnlineRoom,
    OnlineTerminationReason,
    PlayerConnectionState,
    PlayerSlot,
    RoomClock,
    RoomStatus,
)
from backend.online_rooms.manager import RoomManager, room_manager

__all__ = [
    "ColorPreference",
    "OnlineRoom",
    "OnlineTerminationReason",
    "PlayerConnectionState",
    "PlayerSlot",
    "RoomClock",
    "RoomStatus",
    "RoomManager",
    "room_manager",
]

