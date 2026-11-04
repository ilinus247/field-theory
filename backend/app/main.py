import asyncio
import json
import logging
import os
import secrets
import string
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .game import Room, Invalid, ROUNDS
from .physics.streams import Streams
from .transport import Peer, BurstLimit

rooms = {}
locks = {}
MAX_ROOMS = 16
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")


async def broadcast(room):
    # No network waits while holding room locks. A delayed viewer drops old frames.
    if not any(p["id"] == room.host and p["connected"] for p in room.players):
        room.host = next((p["id"] for p in room.players if p["connected"]), room.host)
    room.seq += 1
    payload = {"type": "state", "state": room.public()}
    for p in room.players:
        peer = p.get("peer")
        if peer and p["connected"]:
            peer.offer_state(payload)


async def ticker():
    while True:
        started = time.perf_counter()
        for code, room in list(rooms.items()):
            async with locks[code]:
                now = time.time()
                if (
                    not any(p["connected"] for p in room.players)
                    and now - room.updated > 300
                ):
                    rooms.pop(code, None)
                    locks.pop(code, None)
                    continue
                if not any(p["connected"] for p in room.players):
                    continue
                dirty = bool(room.pending_controls)
                try:
                    room.flush_controls()
                    if room.phase == "construction" and (
                        now >= room.deadline
                        or all(p["ready"] or not p["connected"] for p in room.players)
                    ):
                        room.launch()
                        dirty = True
                    elif room.phase == "simulation":
                        await asyncio.to_thread(room.advance)
                        dirty = True
                    elif room.phase == "results" and now >= room.deadline:
                        dirty = True
                        if room.round >= ROUNDS:
                            room.phase = "finished"
                            room.deadline = None
                        else:
                            room.construct()
                    if dirty:
                        await broadcast(room)
                except Exception:
                    logging.exception("Room simulation failed")
                    room.phase = "finished"
                    room.deadline = None
                    await broadcast(room)
        await asyncio.sleep(max(0.001, 0.1 - (time.perf_counter() - started)))


@asynccontextmanager
async def lifespan(app):
    started = time.perf_counter()
    warm = Streams(4)
    await asyncio.to_thread(
        warm.tick,
        [
            {
                "id": str(i),
                "angle": 0.0,
                "generators": [],
                "connected": True,
                "effects": {},
            }
            for i in range(4)
        ],
        [],
    )
    app.state.physics_startup_seconds = time.perf_counter() - started
    task = asyncio.create_task(ticker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=[]
)


@app.get("/health")
def health():
    import resource, sys

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "status": "ok",
        "engine": "jax-live-boris",
        "network_revision": "queued-controls-v1",
        "rooms": len(rooms),
        "max_tick_ms": round(
            max((r.last_tick_ms for r in rooms.values()), default=0), 2
        ),
        "stream_interactions": True,
        "arena_revision": "match-arenas-v1",
        "physics_startup_seconds": round(app.state.physics_startup_seconds, 3),
        "peak_memory_mb": round(
            rss / (1024**2 if sys.platform == "darwin" else 1024), 1
        ),
    }


@app.websocket("/ws")
async def socket(ws: WebSocket):
    if ws.headers.get("origin") not in origins:
        await ws.close(code=1008)
        return
    await ws.accept()
    room = None
    player = None
    peer = None
    wire_limit = BurstLimit()
    admin_limit = BurstLimit(rate=4, capacity=12)
    try:
        raw = await asyncio.wait_for(ws.receive_text(), 15)
        if len(raw) > 4096:
            raise Invalid("message too large")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise Invalid("invalid message")
        if data.get("type") == "create":
            if len(rooms) >= MAX_ROOMS:
                raise Invalid("all rooms are busy; try again later")
            while True:
                code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(5))
                if code not in rooms:
                    break
            room = Room(code)
            player = room.add(data.get("name"))
            rooms[code] = room
            locks[code] = asyncio.Lock()
        elif data.get("type") == "join":
            code = str(data.get("code", "")).upper()
            room = rooms.get(code)
            if not room:
                raise Invalid("room not found — check the code")
            async with locks[code]:
                player = room.add(data.get("name"), data.get("token"))
        else:
            raise Invalid("create or join a room first")
        async with locks[room.code]:
            old_peer = player.get("peer")
            player["socket"] = ws
            player["connected"] = True

            def failed():
                if player.get("peer") is peer:
                    player["connected"] = False
                    room.updated = time.time()

            peer = Peer(ws, failed)
            player["peer"] = peer
            peer.offer_message(
                {
                    "type": "identity",
                    "id": player["id"],
                    "token": player["token"],
                    "code": room.code,
                }
            )
            room.updated = time.time()
            await broadcast(room)
        if old_peer:
            await old_peer.stop(code=4001)
        async for raw in ws.iter_text():
            try:
                if len(raw) > 4096:
                    raise Invalid("message too large")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise Invalid("invalid message")
                if player.get("peer") is not peer:
                    break
                room.updated = time.time()
                if not wire_limit.allow():
                    logging.warning(
                        "Excessive WebSocket traffic; closing one connection"
                    )
                    await peer.stop(code=1008)
                    break
                action = data.get("type")
                if action == "ping":
                    peer.offer_message(
                        {
                            "type": "pong",
                            "client_time": data.get("client_time"),
                            "server_time": time.time(),
                        }
                    )
                    continue
                if action == "configure":
                    # Coalesce before acquiring the simulation lock: delayed packets
                    # must not build a backlog or be misclassified as rapid input.
                    room.queue_controls(player, data)
                    continue
                if not admin_limit.allow():
                    continue
                async with locks[room.code]:
                    if player.get("peer") is not peer:
                        break
                    room.flush_controls()
                    room.action(player, data)
                    await broadcast(room)
            except (Invalid, ValueError, TypeError, KeyError) as e:
                peer.offer_message(
                    {
                        "type": "error",
                        "message": (
                            str(e) if isinstance(e, Invalid) else "invalid message"
                        ),
                    }
                )
    except (Invalid, ValueError, TypeError, asyncio.TimeoutError) as e:
        try:
            await ws.send_json(
                {
                    "type": "error",
                    "message": (
                        str(e) if isinstance(e, Invalid) else "could not join room"
                    ),
                }
            )
        except Exception:
            pass
    except WebSocketDisconnect:
        pass
    finally:
        if room and player and player["socket"] is ws:
            async with locks[room.code]:
                player["connected"] = False
                player["socket"] = None
                room.updated = time.time()
                if room.host == player["id"]:
                    room.host = next(
                        (p["id"] for p in room.players if p["connected"]), room.host
                    )
                await broadcast(room)
        if peer:
            await peer.stop()
        else:
            try:
                await ws.close()
            except Exception:
                pass
