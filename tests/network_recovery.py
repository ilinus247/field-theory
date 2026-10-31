"""Production regression: a delayed input burst followed by a full live minute of controls.
Usage: python tests/network_recovery.py [wss://host/ws] [https://frontend-origin]
"""

import asyncio, json, math, sys, time
from websockets.asyncio.client import connect

URL = sys.argv[1] if len(sys.argv) > 1 else "wss://field-theory.onrender.com/ws"
ORIGIN = (
    sys.argv[2]
    if len(sys.argv) > 2
    else "https://field-theory.packedbasil2.chatgpt.site"
)


async def send(ws, data):
    await ws.send(json.dumps(data))


async def state(ws, phase=None):
    while True:
        m = json.loads(await asyncio.wait_for(ws.recv(), 15))
        assert m["type"] != "error", m
        if m["type"] == "state" and (phase is None or m["state"]["phase"] == phase):
            return m["state"]


async def main():
    started = time.perf_counter()
    seq = 1
    states = 0
    sent = 0
    async with connect(URL, origin=ORIGIN) as a, connect(URL, origin=ORIGIN) as b:
        await send(a, dict(type="create", name="network-test-a"))
        await a.recv()
        s = await state(a)
        await send(b, dict(type="join", name="network-test-b", code=s["code"]))
        await b.recv()
        await state(b)
        await state(a)
        await send(a, dict(type="start"))
        await asyncio.gather(state(a, "construction"), state(b, "construction"))
        for ws, angle in [(a, 0.1), (b, -math.pi / 2)]:
            await send(
                ws,
                dict(
                    type="ready",
                    match=1,
                    round=1,
                    input_seq=1,
                    angle=angle,
                    generators=[],
                ),
            )
        await asyncio.gather(state(a, "simulation"), state(b, "simulation"))
        # About ten seconds of normal controls arriving together after a network delay.
        for _ in range(120):
            seq += 1
            await send(
                a,
                dict(
                    type="configure",
                    match=1,
                    round=1,
                    input_seq=seq,
                    angle=0.1,
                    generators=[],
                ),
            )
            sent += 1

        async def controls():
            nonlocal seq, sent
            while True:
                seq += 1
                sent += 1
                await send(
                    a,
                    dict(
                        type="configure",
                        match=1,
                        round=1,
                        input_seq=seq,
                        angle=0.1 + 0.02 * math.sin(time.perf_counter() - started),
                        generators=[],
                    ),
                )
                await asyncio.sleep(0.08)

        producer = asyncio.create_task(controls())
        try:
            while True:
                sa, sb = await asyncio.gather(state(a), state(b))
                while sa["seq"] != sb["seq"]:
                    if sa["seq"] < sb["seq"]:
                        sa = await state(a)
                    else:
                        sb = await state(b)
                assert sa == sb
                assert all(p["connected"] for p in sa["players"])
                if sa["phase"] == "results":
                    break
                if sa["live"]["time"] >= 1:
                    assert any(
                        p[1] == 0 for p in sa["live"]["particles"]
                    ), "cannon stopped emitting"
                states += 1
                if states % 100 == 0:
                    print(
                        f'{sa["live"]["time"]:.1f}s: cannon firing, both connected, no errors',
                        flush=True,
                    )
        finally:
            producer.cancel()
            try:
                await producer
            except asyncio.CancelledError:
                pass
        assert sa["live"]["time"] == 60
        print(
            f"PASS: 120-message delay burst + {sent-120} ongoing controls; {states} identical live snapshots; no slowdown errors or firing interruptions ({time.perf_counter()-started:.1f}s)",
            flush=True,
        )


asyncio.run(main())
