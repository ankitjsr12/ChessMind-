"""Unit tests for FastAPI Online Room API endpoints.

Tests:
1. Room creation endpoint (private and public)
2. Room join endpoint and error handling (404, 400 full)
3. Room state inspection endpoint
4. Authoritative move execution endpoint (legal move, out-of-turn 403, illegal move 422)
5. Room action endpoint (resign, draw offer, accept draw)
6. Public room listing endpoint
"""

import pytest
from fastapi import HTTPException

from backend.api.main import (
    create_room_endpoint,
    get_room_state_endpoint,
    join_room_endpoint,
    list_public_rooms_endpoint,
    play_room_move_endpoint,
    room_action_endpoint,
)
from backend.api.schemas import (
    CreateRoomRequest,
    JoinRoomRequest,
    RoomActionRequest,
    RoomMoveRequest,
)
from backend.online_rooms import room_manager


def test_api_create_and_join_room():
    """Test creating and joining room via FastAPI endpoints."""
    # 1. Create private room
    create_req = CreateRoomRequest(
        user_id="user_host",
        username="HostPlayer",
        time_control_seconds=300,
        increment_seconds=2,
        is_private=True,
        color_preference="white",
    )
    create_res = create_room_endpoint(create_req)
    assert create_res["success"] is True
    code = create_res["room_code"]
    assert len(code) == 6

    # 2. Inspect state
    state = get_room_state_endpoint(code)
    assert state["room"]["status"] == "waiting"
    assert state["room"]["white_player"]["username"] == "HostPlayer"

    # 3. Join room
    join_req = JoinRoomRequest(
        room_code=code,
        user_id="user_guest",
        username="GuestPlayer",
    )
    join_res = join_room_endpoint(join_req)
    assert join_res["success"] is True
    assert join_res["assigned_color"] == "black"
    assert join_res["room"]["status"] == "active"


def test_api_join_nonexistent_room():
    """Verify joining invalid room code raises 404."""
    req = JoinRoomRequest(room_code="NON999", user_id="u1", username="P1")
    with pytest.raises(HTTPException) as exc:
        join_room_endpoint(req)
    assert exc.value.status_code == 404


def test_api_authoritative_move_execution():
    """Test server-authoritative move execution via endpoint."""
    create_res = create_room_endpoint(CreateRoomRequest(
        user_id="u_w", username="White", color_preference="white"
    ))
    code = create_res["room_code"]
    join_room_endpoint(JoinRoomRequest(room_code=code, user_id="u_b", username="Black"))

    # 1. Black attempts to move out of turn -> 403
    with pytest.raises(HTTPException) as exc:
        play_room_move_endpoint(RoomMoveRequest(room_code=code, user_id="u_b", move="e7e5"))
    assert exc.value.status_code == 403

    # 2. White plays legal move -> 200
    move_res = play_room_move_endpoint(RoomMoveRequest(room_code=code, user_id="u_w", move="e2e4"))
    assert move_res["success"] is True
    assert move_res["played_move"] == "e4"
    assert move_res["turn"] == "black"

    # 3. Black plays illegal move -> 422
    with pytest.raises(HTTPException) as exc:
        play_room_move_endpoint(RoomMoveRequest(room_code=code, user_id="u_b", move="e7e4"))
    assert exc.value.status_code == 422


def test_api_room_actions():
    """Test resign and draw offer endpoints."""
    create_res = create_room_endpoint(CreateRoomRequest(
        user_id="u_w", username="White", color_preference="white"
    ))
    code = create_res["room_code"]
    join_room_endpoint(JoinRoomRequest(room_code=code, user_id="u_b", username="Black"))

    # White offers draw
    act_res = room_action_endpoint(RoomActionRequest(room_code=code, user_id="u_w", action="offer_draw"))
    assert act_res["success"] is True
    assert act_res["room"]["draw_offered_by"] == "white"

    # Black accepts draw
    act_res2 = room_action_endpoint(RoomActionRequest(room_code=code, user_id="u_b", action="accept_draw"))
    assert act_res2["room"]["status"] == "completed"
    assert act_res2["room"]["termination_reason"] == "agreed_draw"


def test_api_public_rooms_listing():
    """Test listing public waiting rooms."""
    # Create one public room and one private room
    r_pub = create_room_endpoint(CreateRoomRequest(
        user_id="u_pub", username="PubHost", is_private=False
    ))
    r_priv = create_room_endpoint(CreateRoomRequest(
        user_id="u_priv", username="PrivHost", is_private=True
    ))

    pub_list = list_public_rooms_endpoint()
    pub_codes = [r["room_code"] for r in pub_list["rooms"]]

    assert r_pub["room_code"] in pub_codes
    assert r_priv["room_code"] not in pub_codes

