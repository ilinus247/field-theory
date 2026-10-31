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
from .game import Room, Invalid
from .physics.simulation import simulate

rooms = {}
locks = {}
MAX_ROOMS = 64
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")


async def broadcast(room):
    room.seq += 1
    room.updated = time.time()
    payload = {"type": "state", "state": room.public()}
    for p in room.players:
        if p["socket"]:
            try:
                await asyncio.wait_for(p["socket"].send_json(payload), 2)
            except Exception:
                p["connected"] = False
                p["socket"] = None
    if not any(p["id"] == room.host and p["connected"] for p in room.players):
        room.host = next((p["id"] for p in room.players if p["connected"]), room.host)


async def ticker():
    while True:
        await asyncio.sleep(0.15)
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
                if room.phase == "construction" and (
                    now >= room.deadline
                    or all(p["ready"] or not p["connected"] for p in room.players)
                ):
                    room.phase = "computing"
                    await broadcast(room)
                    room.playback = await asyncio.to_thread(
                        simulate,
                        [
                            {k: p[k] for k in ("id", "angle", "generators")}
                            for p in room.players
                        ],
                    )
                    room.playback["start"] = time.time() + 1.2
                    room.phase = "simulation"
                    room.deadline = room.playback["start"] + 8
                    await broadcast(room)
                elif room.deadline and now >= room.deadline:
                    if room.phase == "simulation":
                        for e in room.playback["events"]:
                            if e["scored"]:
                                next(p for p in room.players if p["id"] == e["owner"])[
                                    "score"
                                ] += 1
                        room.phase = "results"
                        room.deadline = now + 4
                        await broadcast(room)
                    elif room.phase == "results":
                        if room.round >= 5:
                            room.phase = "finished"
                            room.deadline = None
                        else:
                            room.construct()
                        await broadcast(room)


@asynccontextmanager
async def lifespan(app):
    started = time.perf_counter()
    await asyncio.to_thread(
        simulate,
        [
            {"id": "warm-a", "angle": 0.0, "generators": []},
            {"id": "warm-b", "angle": 3.141592653589793, "generators": []},
        ],
    )
    app.state.physics_startup_seconds = time.perf_counter() - started
    logging.info(
        "Physics engine %s ready in %.3fs",
        os.getenv("PHYSICS_ENGINE", "jax"),
        app.state.physics_startup_seconds,
    )
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
        "engine": os.getenv("PHYSICS_ENGINE", "jax") + "-boris",
        "rooms": len(rooms),
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
            old = player["socket"]
            player["socket"] = ws
            player["connected"] = True
            if old:
                try:
                    await old.close(code=4001)
                except Exception:
                    pass
            await ws.send_json(
                {
                    "type": "identity",
                    "id": player["id"],
                    "token": player["token"],
                    "code": room.code,
                }
            )
            if not any(p["id"] == room.host and p["connected"] for p in room.players):
                room.host = player["id"]
            await broadcast(room)
        async for raw in ws.iter_text():
            try:
                if len(raw) > 4096:
                    raise Invalid("message too large")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise Invalid("invalid message")
                now = time.time()
                player["rate"] = [t for t in player["rate"] if t > now - 1]
                if len(player["rate"]) >= 30:
                    raise Invalid("slow down")
                player["rate"].append(now)
                if data.get("type") == "ping":
                    await ws.send_json(
                        {
                            "type": "pong",
                            "client_time": data.get("client_time"),
                            "server_time": now,
                        }
                    )
                    continue
                async with locks[room.code]:
                    if player["socket"] is not ws:
                        break
                    room.action(player, data)
                    await broadcast(room)
            except (Invalid, ValueError, TypeError, KeyError) as e:
                await ws.send_json(
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
                if room.host == player["id"]:
                    room.host = next(
                        (p["id"] for p in room.players if p["connected"]), room.host
                    )
                await broadcast(room)
        try:
            await ws.close()
        except Exception:
            pass
