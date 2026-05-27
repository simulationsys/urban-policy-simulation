"""End-to-end smoke test of the live stream — the shape of the daily integration check (ROLE_5)."""

from tests.conftest import make_scenario


def test_ws_streams_ticks(client):
    sid = make_scenario(client)["id"]
    client.post(f"/api/v1/scenarios/{sid}/start")

    with client.websocket_connect(f"/ws/scenarios/{sid}") as ws:
        first = ws.receive_json()
        assert first["type"] == "status"
        assert first["scenario_id"] == sid

        # Then tick frames should flow (fast tick interval set in conftest).
        msg = ws.receive_json()
        assert msg["type"] == "tick"
        assert msg["diff"]["scenario_id"] == sid
        assert "avg_commute_minutes" in msg["diff"]["metrics"]


def test_ws_unknown_scenario_closes(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/scenarios/scenario_9999") as ws:
            ws.receive_json()
