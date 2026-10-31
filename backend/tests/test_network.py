import time
from fastapi.testclient import TestClient
from app.main import app, rooms

ORIGIN = {"origin": "http://localhost:5173"}


def receive_state(ws, phase=None):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "state" and (phase is None or msg["state"]["phase"] == phase):
            return msg["state"]


def test_websocket_match_reconnect_and_independent_rooms():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws", headers=ORIGIN
        ) as a, client.websocket_connect("/ws", headers=ORIGIN) as b:
            a.send_json({"type": "create", "name": "ada"})
            identity = a.receive_json()
            first = receive_state(a)
            code = first["code"]
            b.send_json({"type": "join", "name": "ben", "code": code})
            bid = b.receive_json()
            receive_state(b)
            receive_state(a)
            with client.websocket_connect("/ws", headers=ORIGIN) as other:
                other.send_json({"type": "create", "name": "third"})
                other.receive_json()
                os = receive_state(other)
                assert os["code"] != code
            a.send_json({"type": "start"})
            receive_state(a, "construction")
            receive_state(b, "construction")
            for number in range(1, 4):
                for ws, angle in [(a, 0), (b, 3.141592653589793)]:
                    ws.send_json(
                        dict(
                            type="ready",
                            input_seq=number,
                            match=1,
                            round=number,
                            angle=angle,
                            generators=[],
                        )
                    )
                sa = receive_state(a, "simulation")
                sb = receive_state(b, "simulation")
                assert sa["live"] == sb["live"]
                assert sa["seq"] == sb["seq"]
                assert sa["rules"] == {
                    "rounds": 3,
                    "setup_seconds": 8,
                    "live_seconds": 60,
                }
                assert sa["round"] == number
                rooms[code].live.time = 59.9
                ra = receive_state(a, "results")
                rb = receive_state(b, "results")
                assert ra["players"] == rb["players"]
                assert ra["players"][0]["score"] >= 0
                rooms[code].deadline = time.time() - 0.1
                phase = "finished" if number == 3 else "construction"
                receive_state(a, phase)
                final = receive_state(b, phase)
            assert final["players"][0]["score"] == final["players"][1]["score"] == 0
            a.send_json({"type": "rematch"})
            receive_state(a, "construction")
            receive_state(b, "construction")
            with client.websocket_connect("/ws", headers=ORIGIN) as refreshed:
                refreshed.send_json(
                    dict(type="join", code=code, name="ada", token=identity["token"])
                )
                newid = refreshed.receive_json()
                assert newid["id"] == identity["id"]
                s = receive_state(refreshed)
                assert len(s["players"]) == 2
                refreshed.send_json(
                    dict(type="ready", match=1, round=0, angle=0, generators=[])
                )
                while refreshed.receive_json()["type"] != "error":
                    pass
                refreshed.send_text("{broken")
                while refreshed.receive_json()["type"] != "error":
                    pass
                refreshed.send_text("[]")
                while refreshed.receive_json()["type"] != "error":
                    pass


def test_bad_code_and_origin():
    with TestClient(app) as c:
        with c.websocket_connect("/ws", headers=ORIGIN) as ws:
            ws.send_json(dict(type="join", name="a", code="XXXXX"))
            assert "not found" in ws.receive_json()["message"]
