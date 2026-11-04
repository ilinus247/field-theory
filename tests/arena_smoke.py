"""Two-client arena selection, lock, placement rejection, and live snapshot check.
Usage: python tests/arena_smoke.py [ws(s)://host/ws] [frontend-origin]
"""

import asyncio
import json
import sys
from websockets.asyncio.client import connect
from live_smoke import message, state, send, paired

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws"
ORIGIN = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5173"


async def check(arena):
    async with connect(URL, origin=ORIGIN) as a, connect(URL, origin=ORIGIN) as b:
        await send(a, dict(type="create", name="arena-qa-a"))
        await message(a)
        s = await state(a)
        await send(b, dict(type="join", name="arena-qa-b", code=s["code"]))
        await message(b)
        await state(b)
        await state(a)
        await send(a, dict(type="arena", arena=arena))
        s = await paired(a, b)
        assert s["arena"]["id"] == arena and len(s["arena"]["objects"]) == 2
        await send(a, dict(type="start"))
        s = await paired(a, b)
        assert s["phase"] == "construction"
        await send(a, dict(type="arena", arena="open"))
        assert json.loads(await a.recv())["type"] == "error"
        # Illegal fixed-object overlap must be rejected before it enters simulation.
        await send(
            a,
            dict(
                type="ready",
                match=1,
                round=1,
                input_seq=1,
                angle=0,
                generators=[dict(kind="coil", x=0.5, y=0.3)],
            ),
        )
        assert json.loads(await a.recv())["type"] == "error"
        for ws, angle in ((a, -0.35), (b, 3.5)):
            await send(
                ws,
                dict(
                    type="ready",
                    match=1,
                    round=1,
                    input_seq=2,
                    angle=angle,
                    generators=[],
                ),
            )
        count = 0
        while True:
            s = await paired(a, b)
            assert s["arena"]["id"] == arena
            if s["phase"] == "simulation":
                count += 1
                if s["live"]["time"] >= 8:
                    assert s["live"]["particles"]
                    break
        print(
            f"PASS {arena}: {count} identical live snapshots; host selection, lock and overlap checks"
        )


async def main():
    for arena in ("lenses", "eddies"):
        await check(arena)


asyncio.run(main())
