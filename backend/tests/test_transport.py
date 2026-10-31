import asyncio, time
import numpy as np
from fastapi.testclient import TestClient
from app.transport import BurstLimit, Peer
from app.game import Room
from app.main import app, broadcast, rooms


def test_delay_burst_uses_latest_controls_without_warning_or_stopping_emission():
    r = Room("BURST")
    a = r.add("a")
    r.add("b")
    r.construct()
    r.launch()
    for i in range(1, 121):
        assert r.queue_controls(
            a,
            dict(
                type="configure",
                round=1,
                match=1,
                input_seq=i,
                angle=i * 0.001,
                generators=[],
            ),
        )
    assert len(r.pending_controls) == 1
    r.flush_controls()
    assert a["angle"] == 0.12 and r.input_seq[a["id"]] == 120
    for _ in range(20):
        r.advance()
    assert a["connected"] and np.asarray(r.live.state[3])[0] > 0
    assert any(p[1] == 0 for p in r.live.snapshot()["particles"])


def test_burst_limit_accepts_delayed_normal_controls_but_bounds_floods():
    limit = BurstLimit()
    start = limit.at
    assert all(limit.allow(start) for _ in range(600))
    assert not limit.allow(start)
    assert all(limit.allow(start + 1) for _ in range(60))
    assert not limit.allow(start + 1)


def test_slow_viewer_drops_obsolete_frames_and_does_not_stop_the_cannon():
    async def run():
        gate = asyncio.Event()
        started = asyncio.Event()
        failed = []

        class Slow:
            def __init__(self):
                self.sent = []

            async def send_json(self, payload):
                started.set()
                if not self.sent:
                    await gate.wait()
                self.sent.append(payload)

            async def close(self, **kwargs):
                pass

        socket = Slow()
        r = Room("SLOWA")
        a = r.add("a")
        r.add("b")
        r.construct()
        r.launch()
        peer = Peer(socket, lambda: failed.append(True))
        a["peer"] = peer
        a["socket"] = socket
        try:
            before = time.perf_counter()
            await broadcast(r)
            assert time.perf_counter() - before < 0.1
            await started.wait()
            await asyncio.sleep(0.3)
            for _ in range(20):
                r.advance()
                await broadcast(r)
            assert a["connected"] and not failed
            assert peer.latest["state"]["seq"] == r.seq
            assert len(peer.messages) == 0
            assert r.live.time == 2
            assert any(p[1] == 0 for p in r.live.snapshot()["particles"])
            gate.set()
            for _ in range(20):
                if len(socket.sent) >= 2:
                    break
                await asyncio.sleep(0.01)
            assert len(socket.sent) == 2
            assert socket.sent[-1]["state"]["seq"] == r.seq
        finally:
            await peer.stop()

    asyncio.run(run())


def test_network_delayed_control_burst_has_no_slow_down_errors():
    rooms.clear()
    headers = {"origin": "http://localhost:5173"}

    def state(ws, phase=None):
        while True:
            m = ws.receive_json()
            assert m["type"] != "error", m
            if m["type"] == "state" and (phase is None or m["state"]["phase"] == phase):
                return m["state"]

    with TestClient(app) as c:
        with c.websocket_connect("/ws", headers=headers) as a, c.websocket_connect(
            "/ws", headers=headers
        ) as b:
            a.send_json(dict(type="create", name="a"))
            a.receive_json()
            s = state(a)
            code = s["code"]
            b.send_json(dict(type="join", name="b", code=code))
            b.receive_json()
            state(b)
            state(a)
            a.send_json(dict(type="start"))
            state(a, "construction")
            state(b, "construction")
            for i in range(1, 121):
                a.send_json(
                    dict(
                        type="configure",
                        round=1,
                        match=1,
                        input_seq=i,
                        angle=i * 0.001,
                        generators=[],
                    )
                )
            a.send_json(dict(type="ping", client_time=1))
            while True:
                m = a.receive_json()
                assert m["type"] != "error", m
                if m["type"] == "pong":
                    break
            while state(a)["players"][0]["angle"] != 0.12:
                pass
            a.send_json(
                dict(
                    type="ready",
                    round=1,
                    match=1,
                    input_seq=121,
                    angle=0.12,
                    generators=[],
                )
            )
            b.send_json(
                dict(
                    type="ready",
                    round=1,
                    match=1,
                    input_seq=1,
                    angle=3.14,
                    generators=[],
                )
            )
            s = state(a, "simulation")
            while s["live"]["time"] < 1:
                s = state(a, "simulation")
            assert s["players"][0]["connected"]
            assert any(p[1] == 0 for p in s["live"]["particles"])


def test_refresh_closes_replaced_socket_without_reconnect_ping_pong():
    headers = {"origin": "http://localhost:5173"}
    with TestClient(app) as c:
        with c.websocket_connect("/ws", headers=headers) as old:
            old.send_json(dict(type="create", name="a"))
            identity = old.receive_json()
            old.receive_json()
            with c.websocket_connect("/ws", headers=headers) as new:
                new.send_json(
                    dict(
                        type="join",
                        name="a",
                        code=identity["code"],
                        token=identity["token"],
                    )
                )
                assert new.receive_json()["id"] == identity["id"]
                assert new.receive_json()["state"]["players"][0]["connected"]
                while True:
                    message = old.receive()
                    if message["type"] == "websocket.close":
                        assert message["code"] == 4001
                        break
