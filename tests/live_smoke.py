"""Three real 60-second rounds through WebSockets; validates live input and shared snapshots.
Usage: python tests/live_smoke.py [wss://host/ws] [https://frontend-origin]
"""

import asyncio, json, sys, time, math
from websockets.asyncio.client import connect

URL = sys.argv[1] if len(sys.argv) > 1 else "wss://field-theory.onrender.com/ws"
ORIGIN = (
    sys.argv[2]
    if len(sys.argv) > 2
    else "https://field-theory.packedbasil2.chatgpt.site"
)


async def message(ws):
    m = json.loads(await asyncio.wait_for(ws.recv(), 30))
    if m["type"] == "error":
        raise AssertionError(m["message"])
    return m


async def state(ws, phase=None):
    while True:
        m = await message(ws)
        if m["type"] == "state" and (phase is None or m["state"]["phase"] == phase):
            return m["state"]


async def send(ws, data):
    await ws.send(json.dumps(data))


async def paired(a, b):
    sa, sb = await asyncio.gather(state(a), state(b))
    while sa["seq"] != sb["seq"]:
        if sa["seq"] < sb["seq"]:
            sa = await state(a)
        else:
            sb = await state(b)
    assert sa == sb, "authoritative snapshots diverged"
    return sa


async def main():
    started = time.perf_counter()
    seq = 0
    seen_pickups = False
    seen_particles = False
    async with connect(URL, origin=ORIGIN, max_size=1_000_000) as a, connect(
        URL, origin=ORIGIN, max_size=1_000_000
    ) as b:
        await send(a, dict(type="create", name="stream-test-a"))
        identity = await message(a)
        s = await state(a)
        code = s["code"]
        await send(b, dict(type="join", name="stream-test-b", code=code))
        await message(b)
        await state(b)
        await state(a)
        await send(a, dict(type="start"))
        await asyncio.gather(state(a, "construction"), state(b, "construction"))
        for number in range(1, 4):
            seq += 1
            for ws, angle in [(a, 0), (b, -math.pi / 2)]:
                await send(
                    ws,
                    dict(
                        type="ready",
                        match=1,
                        round=number,
                        input_seq=seq,
                        angle=angle,
                        generators=[],
                    ),
                )
            await asyncio.gather(state(a, "simulation"), state(b, "simulation"))
            checks = 0
            changed = False
            removed = False
            while True:
                s = await paired(a, b)
                if s["phase"] == "results":
                    break
                seen_particles |= bool(s["live"]["particles"])
                seen_pickups |= bool(s["boosters"])
                checks += 1
                if s["live"]["time"] >= 1 and not changed:
                    seq += 1
                    await send(
                        a,
                        dict(
                            type="configure",
                            match=1,
                            round=number,
                            input_seq=seq,
                            angle=0.04,
                            generators=[dict(kind="negative", x=0.5, y=0.8)],
                        ),
                    )
                    changed = True
                if s["live"]["time"] >= 3 and not removed:
                    assert s["players"][0][
                        "generators"
                    ], "live placement was not accepted"
                    seq += 1
                    await send(
                        a,
                        dict(
                            type="configure",
                            match=1,
                            round=number,
                            input_seq=seq,
                            angle=0,
                            generators=[],
                        ),
                    )
                    removed = True
                if s["live"]["time"] >= 4:
                    assert not s["players"][0][
                        "generators"
                    ], "live removal was not accepted"
            assert s["live"]["time"] >= 60
            print(
                f'round {number}: {checks} identical live snapshots, scores {[round(p["score"],2) for p in s["players"]]}',
                flush=True,
            )
            end = "finished" if number == 3 else "construction"
            await asyncio.gather(state(a, end), state(b, end))
        assert seen_particles and seen_pickups
        assert any(
            p["score"] > 0 for p in s["players"]
        ), "continuous contact never scored"
        await send(a, dict(type="rematch"))
        await asyncio.gather(state(a, "construction"), state(b, "construction"))
        async with connect(URL, origin=ORIGIN) as fresh:
            await send(
                fresh,
                dict(
                    type="join",
                    name="stream-test-a",
                    code=code,
                    token=identity["token"],
                ),
            )
            i = await message(fresh)
            assert i["id"] == identity["id"]
            s = await state(fresh)
            assert len(s["players"]) == 2 and s["match"] == 2
        print(
            f"PASS: three full live rounds, shared JAX snapshots, live controls, boosters, scoring, rematch, reconnect ({time.perf_counter()-started:.1f}s)",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
