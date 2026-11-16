"""Automated unit and integration tests for ChessMind AI Backend Health and WebSocket Endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.online_rooms import room_manager
from backend.api.schemas import CreateRoomRequest
from backend.api.main import create_room_endpoint


@pytest.fixture
def client():
    return TestClient(app)


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "ChessMind AI Backend API"
    assert data["status"] == "online"


def test_health_endpoints(client):
    # Test both /api/health and /health
    for endpoint in ["/api/health", "/health"]:
        response = client.get(endpoint)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "modules" in data
        assert data["modules"]["chess_engine"] is True
        assert data["modules"]["minimax_predictor"] is True
        assert data["modules"]["opponent_search"] is True
        assert data["modules"]["online_rooms"] is True
        assert "active_rooms" in data


def test_websocket_ping_pong(client):
    with client.websocket_connect("/ws") as ws:
        connected = ws.receive_json()
        assert connected["type"] == "connected"
        assert "ChessMind AI" in connected["service"]

        # Send ping
        ws.send_text("ping")
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert "timestamp" in pong


def test_websocket_room_lifecycle(client):
    # Create room
    create_req = CreateRoomRequest(
        user_id="ws_user_1",
        username="WSPlayer1",
        time_control_seconds=300,
        increment_seconds=0,
        is_private=True,
    )
    res = create_room_endpoint(create_req)
    assert res["success"] is True
    code = res["room_code"]

    with client.websocket_connect(f"/ws/rooms/{code}") as ws:
        init_state = ws.receive_json()
        assert init_state["type"] == "room_state"
        assert init_state["room_code"] == code

        # Ping room
        ws.send_json({"action": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert pong["room_code"] == code
