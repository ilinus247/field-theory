"""Room state and validation, independent of WebSocket transport."""

import math
import secrets
import time
from .physics.simulation import reactors, PROTECTED_RADIUS


class Invalid(ValueError):
    pass


def validate_config(data, count):
    angle = data.get("angle")
    generators = data.get("generators")
    if (
        isinstance(angle, bool)
        or not isinstance(angle, (int, float))
        or not math.isfinite(angle)
    ):
        raise Invalid("choose a valid angle")
    if not isinstance(generators, list) or len(generators) > 2:
        raise Invalid("place at most two fields")
    result = []
    coils = 0
    for g in generators:
        if not isinstance(g, dict) or g.get("kind") not in (
            "positive",
            "negative",
            "coil",
        ):
            raise Invalid("unknown field")
        x, y = g.get("x"), g.get("y")
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not 0.025 <= v <= 0.975
            for v in (x, y)
        ):
            raise Invalid("keep fields inside the arena")
        if any(
            math.hypot(x - cx, y - cy) < PROTECTED_RADIUS for cx, cy in reactors(count)
        ):
            raise Invalid("keep fields outside reactor circles")
        coils += g["kind"] == "coil"
        result.append({"kind": g["kind"], "x": x, "y": y})
    if coils > 1:
        raise Invalid("one magnetic coil per player")
    return angle % (2 * math.pi), result


class Room:
    def __init__(self, code):
        self.code = code
        self.players = []
        self.phase = "lobby"
        self.round = 0
        self.match = 1
        self.seq = 0
        self.deadline = None
        self.playback = None
        self.updated = time.time()
        self.host = None

    def public(self):
        return {
            "code": self.code,
            "players": [
                {k: v for k, v in p.items() if k not in ("token", "socket", "rate")}
                for p in self.players
            ],
            "phase": self.phase,
            "round": self.round,
            "match": self.match,
            "seq": self.seq,
            "deadline": self.deadline,
            "playback": self.playback,
            "host": self.host,
            "server_time": time.time(),
        }

    def add(self, name, token=None):
        for p in self.players:
            if token and secrets.compare_digest(p["token"], token):
                return p
        if self.phase != "lobby":
            raise Invalid("this match has already started")
        if len(self.players) >= 4:
            raise Invalid("room is full")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 20:
            raise Invalid("use a name of 1–20 characters")
        p = {
            "id": secrets.token_hex(6),
            "token": secrets.token_urlsafe(24),
            "name": name.strip(),
            "score": 0,
            "ready": False,
            "connected": True,
            "angle": 0.0,
            "generators": [],
            "socket": None,
            "rate": [],
        }
        self.players.append(p)
        if not self.host:
            self.host = p["id"]
        return p

    def construct(self):
        self.round += 1
        self.phase = "construction"
        self.deadline = time.time() + 20
        self.playback = None
        for i, p in enumerate(self.players):
            x, y = reactors(len(self.players))[i]
            p.update(ready=False, generators=[], angle=math.atan2(0.5 - y, 0.5 - x))

    def action(self, p, data):
        action = data.get("type")
        if action == "start":
            if (
                p["id"] != self.host
                or self.phase != "lobby"
                or sum(x["connected"] for x in self.players) < 2
            ):
                raise Invalid("host needs at least two connected players")
            self.players = [x for x in self.players if x["connected"]]
            self.construct()
        elif action in ("configure", "ready"):
            if (
                self.phase != "construction"
                or data.get("round") != self.round
                or data.get("match") != self.match
            ):
                raise Invalid("this round is locked")
            angle, generators = validate_config(data, len(self.players))
            p.update(angle=angle, generators=generators, ready=action == "ready")
        elif action == "rematch":
            if self.phase != "finished" or p["id"] != self.host:
                raise Invalid("host can start a rematch after the match")
            self.players = [x for x in self.players if x["connected"]]
            if len(self.players) < 2:
                raise Invalid("two players needed for rematch")
            self.round = 0
            self.match += 1
            for x in self.players:
                x["score"] = 0
            self.construct()
        else:
            raise Invalid("unknown action")
