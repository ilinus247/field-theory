"""Bounded WebSocket output and burst-tolerant input protection.

A slow viewer keeps at most one pending state snapshot, never a history of frames.
Only this connection's writer sends frames, so pongs/errors cannot race snapshots.
"""

import asyncio
import time
from collections import deque


class BurstLimit:
    def __init__(self, rate=60.0, capacity=600.0):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.at = time.monotonic()

    def allow(self, now=None):
        now = time.monotonic() if now is None else now
        self.tokens = min(
            self.capacity, self.tokens + max(0, now - self.at) * self.rate
        )
        self.at = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


class Peer:
    def __init__(self, socket, on_failure, send_timeout=5.0):
        self.socket = socket
        self.on_failure = on_failure
        self.send_timeout = send_timeout
        self.latest = None
        self.messages = deque(maxlen=8)
        self.wake = asyncio.Event()
        self.closed = False
        self.task = asyncio.create_task(self.run())

    def offer_state(self, payload):
        if not self.closed:
            self.latest = payload
            self.wake.set()

    def offer_message(self, payload):
        if not self.closed:
            self.messages.append(payload)
            self.wake.set()

    async def run(self):
        try:
            while True:
                await self.wake.wait()
                while self.messages or self.latest is not None:
                    if self.messages:
                        payload = self.messages.popleft()
                    else:
                        payload = self.latest
                        self.latest = None
                    await asyncio.wait_for(
                        self.socket.send_json(payload), self.send_timeout
                    )
                self.wake.clear()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.closed = True
            self.on_failure()
            try:
                await asyncio.wait_for(self.socket.close(code=1013), 1)
            except Exception:
                pass

    async def stop(self, code=1000):
        self.closed = True
        self.latest = None
        self.messages.clear()
        self.task.cancel()
        try:
            await self.task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await asyncio.wait_for(self.socket.close(code=code), 1)
        except Exception:
            pass
