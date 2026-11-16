"""Unit and integration tests for Online 1v1 Room Management and Authoritative Clocks.

Tests:
1. Room code uniqueness and character sanitization
2. Room creation and creator seating
3. Player slot filling and fair color assignment (WHITE, BLACK, RANDOM)
4. Rejection of 3rd player joining a full room
5. Server-authoritative move validation and turn ownership enforcement
6. Authoritative clock management, increments, and flag fall timeout detection
7. Resignation and draw offer / accept / decline handshakes
8. Player reconnection handling
9. Concurrent room creation and joining (multi-threaded race-condition testing)
10. Database serialization (`to_persisted_dict`) and state hydration (`from_persisted_game`)
"""

import concurrent.futures
import time
import pytest

import chess

from backend.chess_engine import IllegalMoveError
from backend.chess_engine.models import PieceColor
from backend.online_rooms import (
    ColorPreference,
    OnlineRoom,
    OnlineTerminationReason,
    PlayerConnectionState,
    RoomClock,
    RoomManager,
    RoomStatus,
)


def test_room_code_uniqueness_and_alphabet():
    """Verify generated room codes are unique, 6 chars, and exclude confusing characters."""
    manager = RoomManager()
    codes = set()
    for _ in range(500):
        code = manager.generate_unique_code()
        assert len(code) == 6
        assert all(c in manager.CODE_ALPHABET for c in code)
        assert code == code.upper()
        # Verify excluded ambiguous characters: 0, O, 1, I
        assert "0" not in code
        assert "O" not in code
        assert "1" not in code
        assert "I" not in code
        codes.add(code)
    assert len(codes) == 500


def test_room_creation():
    """Verify room creation properly seats creator and initializes clock."""
    manager = RoomManager()
    room = manager.create_room(
        creator_user_id="user_alice",
        creator_username="Alice",
        time_control_seconds=300,
        increment_seconds=5,
        is_private=True,
        color_preference=ColorPreference.WHITE,
    )

    assert room.status == RoomStatus.WAITING
    assert room.creator_user_id == "user_alice"
    assert room.time_control_seconds == 300
    assert room.increment_seconds == 5
    assert room.is_private is True
    assert room.white_player is not None
    assert room.white_player.user_id == "user_alice"
    assert room.black_player is None
    assert not room.is_full()
    assert manager.get_room(room.room_code) is room


def test_player_joining_and_fair_color_assignment():
    """Verify joining room seats second player and starts game."""
    # 1. White preference
    mgr1 = RoomManager()
    r1 = mgr1.create_room("u1", "P1", color_preference=ColorPreference.WHITE)
    _, slot1 = mgr1.join_room(r1.room_code, "u2", "P2")
    assert r1.status == RoomStatus.ACTIVE
    assert r1.is_full()
    assert r1.white_player.user_id == "u1"
    assert r1.black_player.user_id == "u2"
    assert slot1.assigned_color == PieceColor.BLACK

    # 2. Black preference
    mgr2 = RoomManager()
    r2 = mgr2.create_room("u1", "P1", color_preference=ColorPreference.BLACK)
    _, slot2 = mgr2.join_room(r2.room_code, "u2", "P2")
    assert r2.status == RoomStatus.ACTIVE
    assert r2.white_player.user_id == "u2"
    assert r2.black_player.user_id == "u1"
    assert slot2.assigned_color == PieceColor.WHITE

    # 3. Random preference
    mgr3 = RoomManager()
    r3 = mgr3.create_room("u1", "P1", color_preference=ColorPreference.RANDOM)
    _, slot3 = mgr3.join_room(r3.room_code, "u2", "P2")
    assert r3.status == RoomStatus.ACTIVE
    colors = {r3.white_player.user_id, r3.black_player.user_id}
    assert colors == {"u1", "u2"}


def test_rejection_of_third_player():
    """Verify third party cannot join a full game room."""
    manager = RoomManager()
    room = manager.create_room("u1", "Alice")
    manager.join_room(room.room_code, "u2", "Bob")

    with pytest.raises(ValueError, match="full"):
        manager.join_room(room.room_code, "u3", "Charlie")


def test_reconnection_idempotency():
    """Verify an existing player reconnecting returns their existing slot."""
    manager = RoomManager()
    room = manager.create_room("u1", "Alice")
    manager.join_room(room.room_code, "u2", "Bob")

    # Disconnect Bob
    manager.set_player_connection_state(room.room_code, "u2", PlayerConnectionState.DISCONNECTED)
    assert room.get_player_by_id("u2").connection_state == PlayerConnectionState.DISCONNECTED

    # Reconnect Bob
    _, slot = manager.join_room(room.room_code, "u2", "Bob")
    assert slot.user_id == "u2"
    assert slot.connection_state == PlayerConnectionState.CONNECTED


def test_server_authoritative_move_validation():
    """Verify moves are checked on server for turn ownership and legality."""
    manager = RoomManager()
    room = manager.create_room("u_white", "WhitePlayer", color_preference=ColorPreference.WHITE)
    manager.join_room(room.room_code, "u_black", "BlackPlayer")

    # 1. Non-seated user cannot play
    with pytest.raises(PermissionError):
        room.make_authoritative_move("intruder", "e2e4")

    # 2. Black cannot play out of turn
    with pytest.raises(PermissionError, match="Not your turn"):
        room.make_authoritative_move("u_black", "e7e5")

    # 3. White plays valid move e2e4
    res = room.make_authoritative_move("u_white", "e2e4")
    assert res.move_record.san == "e4"
    assert room.engine.turn == PieceColor.BLACK

    # 4. White cannot play twice in a row
    with pytest.raises(PermissionError, match="Not your turn"):
        room.make_authoritative_move("u_white", "d2d4")

    # 5. Black plays illegal move
    with pytest.raises(IllegalMoveError):
        room.make_authoritative_move("u_black", "e7e4")

    # 6. Black plays valid reply e7e5
    res2 = room.make_authoritative_move("u_black", "e7e5")
    assert res2.move_record.san == "e5"
    assert room.engine.turn == PieceColor.WHITE


def test_clock_deduction_and_increment():
    """Verify authoritative clock decrements elapsed time and applies increment."""
    clock = RoomClock.create(base_time_seconds=60, increment_seconds=3)
    t0 = 1000.0
    clock.start(PieceColor.WHITE, timestamp=t0)

    # 5 seconds elapsed for White move
    t1 = t0 + 5.0
    w_ms, b_ms = clock.record_move(
        moving_color=PieceColor.WHITE,
        next_turn=PieceColor.BLACK,
        timestamp=t1,
    )

    # Base 60,000 - 5,000 + 3,000 increment = 58,000 ms
    assert w_ms == 58000
    assert b_ms == 60000

    # 2 seconds elapsed for Black move
    t2 = t1 + 2.0
    w_ms, b_ms = clock.record_move(
        moving_color=PieceColor.BLACK,
        next_turn=PieceColor.WHITE,
        timestamp=t2,
    )
    # Base 60,000 - 2,000 + 3,000 increment = 61,000 ms
    assert b_ms == 61000
    assert w_ms == 58000


def test_flag_fall_timeout_game_over():
    """Verify player running out of time triggers timeout win for opponent."""
    manager = RoomManager()
    room = manager.create_room("u_white", "White", time_control_seconds=10, color_preference=ColorPreference.WHITE)
    manager.join_room(room.room_code, "u_black", "Black")

    t_start = 2000.0
    room.clock.start(PieceColor.WHITE, timestamp=t_start)

    # 15 seconds pass without White moving (base was 10s)
    t_now = t_start + 15.0

    # Move attempt should raise ValueError and finish game
    with pytest.raises(ValueError, match="ran out of time"):
        room.make_authoritative_move("u_white", "e2e4", timestamp=t_now)

    assert room.status == RoomStatus.COMPLETED
    assert room.termination_reason == OnlineTerminationReason.TIMEOUT
    assert room.winner_color == PieceColor.BLACK
    assert room.winner_id == "u_black"


def test_resignation_flow():
    """Verify player resignation awards win to opponent."""
    manager = RoomManager()
    room = manager.create_room("u_white", "White", color_preference=ColorPreference.WHITE)
    manager.join_room(room.room_code, "u_black", "Black")

    assert room.status == RoomStatus.ACTIVE
    ok = room.resign("u_black")
    assert ok is True

    assert room.status == RoomStatus.COMPLETED
    assert room.termination_reason == OnlineTerminationReason.RESIGNATION
    assert room.winner_color == PieceColor.WHITE
    assert room.winner_id == "u_white"


def test_draw_offer_handshake():
    """Verify draw offer, decline, and accept flows."""
    manager = RoomManager()
    room = manager.create_room("u_white", "White", color_preference=ColorPreference.WHITE)
    manager.join_room(room.room_code, "u_black", "Black")

    # 1. White offers draw
    room.offer_draw("u_white")
    assert room.draw_offered_by == PieceColor.WHITE

    # 2. Black declines
    room.decline_draw("u_black")
    assert room.draw_offered_by is None

    # 3. Black offers draw
    room.offer_draw("u_black")
    assert room.draw_offered_by == PieceColor.BLACK

    # 4. White cannot accept own offer
    assert not room.accept_draw("u_black")

    # 5. White accepts Black's draw offer
    accepted = room.accept_draw("u_white")
    assert accepted is True
    assert room.status == RoomStatus.COMPLETED
    assert room.termination_reason == OnlineTerminationReason.AGREED_DRAW
    assert room.winner_color is None
    assert room.winner_id is None


def test_concurrent_room_creation_and_joining():
    """Thread-safety test creating and joining rooms concurrently across threads."""
    manager = RoomManager()
    created_codes = []

    def create_worker(idx: int):
        r = manager.create_room(
            creator_user_id=f"user_{idx}",
            creator_username=f"Player_{idx}",
            time_control_seconds=300,
        )
        return r.room_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(create_worker, i) for i in range(40)]
        for f in concurrent.futures.as_completed(futures):
            created_codes.append(f.result())

    assert len(created_codes) == 40
    assert len(set(created_codes)) == 40  # All unique codes

    # Concurrently join all 40 rooms
    def join_worker(code: str, idx: int):
        return manager.join_room(code, user_id=f"joiner_{idx}", username=f"Joiner_{idx}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(join_worker, code, i) for i, code in enumerate(created_codes)]
        for f in concurrent.futures.as_completed(futures):
            room, slot = f.result()
            assert room.is_full()
            assert room.status == RoomStatus.ACTIVE


def test_persisted_serialization_and_hydration():
    """Verify room serializes to Supabase schema and hydrates back correctly."""
    room = OnlineRoom(
        room_code="TEST99",
        creator_user_id="user_creator",
        creator_username="Creator",
        time_control_seconds=600,
        increment_seconds=5,
        is_private=True,
    )
    room.add_player("user_joiner", "Joiner")
    room.make_authoritative_move(room.white_player.user_id, "e2e4")

    # Serialize
    persisted = room.to_persisted_dict()
    assert persisted["room_code"] == "TEST99"
    assert persisted["is_private"] is True
    assert persisted["game_mode"] == "online_1v1_private"
    assert "e4" in persisted["pgn"]

    # Hydrate back
    hydrated = OnlineRoom.from_persisted_game(
        game_data={
            "room_code": persisted["room_code"],
            "user_id": persisted["user_id"],
            "white_player_id": persisted["white_player_id"],
            "black_player_id": persisted["black_player_id"],
            "time_control_seconds": persisted["time_control_seconds"],
            "increment_seconds": persisted["increment_seconds"],
            "is_private": persisted["is_private"],
            "status": persisted["status"],
            "current_fen": persisted["current_fen"],
        }
    )

    assert hydrated.room_code == "TEST99"
    assert hydrated.white_player.user_id == persisted["white_player_id"]
    assert hydrated.black_player.user_id == persisted["black_player_id"]
    assert hydrated.engine.fen == persisted["current_fen"]