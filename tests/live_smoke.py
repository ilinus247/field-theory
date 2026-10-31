"""Run against an actual WSS server. Creates temporary rooms; never logs player tokens.
Usage: python tests/live_smoke.py [wss://host/ws] [https://frontend-origin]
"""

import asyncio
import json
import sys
import time
from websockets.asyncio.client import connect

URL = sys.argv[1] if len(sys.argv) > 1 else "wss://field-theory.onrender.com/ws"
ORIGIN = (
    sys.argv[2]
    if len(sys.argv) > 2
    else "https://field-theory.packedbasil2.chatgpt.site"
)


async def receive(ws, phase=None):
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), 50))
        if msg["type"] == "error":
            raise AssertionError(msg["message"])
        if msg["type"] == "state" and (phase is None or msg["state"]["phase"] == phase):
            return msg["state"]


async def send(ws, data):
    await ws.send(json.dumps(data))


async def main():
    start = time.perf_counter()
    async with connect(URL, origin=ORIGIN) as a, connect(URL, origin=ORIGIN) as b:
        await send(a, dict(type="create", name="live-test-a"))
        identity = json.loads(await a.recv())
        state = await receive(a)
        code = state["code"]
        await send(b, dict(type="join", name="live-test-b", code=code))
        await b.recv()
        await receive(b)
        await receive(a)
        await send(a, dict(type="start"))
        await receive(a, "construction")
        await receive(b, "construction")
        for number in range(1, 6):
            for ws, angle in [(a, 0), (b, 3.141592653589793)]:
                await send(
                    ws, dict(type="ready", round=number, angle=angle, generators=[])
                )
            sa, sb = await asyncio.gather(
                receive(a, "simulation"), receive(b, "simulation")
            )
            assert sa["playback"] == sb["playback"] and sa["round"] == number
            ra, rb = await asyncio.gather(receive(a, "results"), receive(b, "results"))
            assert (
                ra["players"] == rb["players"] and ra["players"][0]["score"] == number
            )
            print(
                f"round {number}: identical playback and scores; {number}–{number}",
                flush=True,
            )
            phase = "finished" if number == 5 else "construction"
            await asyncio.gather(receive(a, phase), receive(b, phase))
        await send(a, dict(type="rematch"))
        await asyncio.gather(receive(a, "construction"), receive(b, "construction"))
        async with connect(URL, origin=ORIGIN) as refreshed:
            await send(
                refreshed,
                dict(
                    type="join", name="live-test-a", code=code, token=identity["token"]
                ),
            )
            again = json.loads(await refreshed.recv())
            assert again["id"] == identity["id"]
            s = await receive(refreshed)
            assert len(s["players"]) == 2
        print(
            f"PASS: real WSS five-round tie, rematch, refresh identity ({time.perf_counter()-start:.1f}s)",
            flush=True,
        )


asyncio.run(main())
