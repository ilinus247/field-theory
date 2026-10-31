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
        or abs(angle) > 1e6
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
            or not 0.025 <= v <= 0.975
            or not math.isfinite(v)
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


SETUP_SECONDS = 8
LIVE_SECONDS = 60
ROUNDS = 3
BOOSTERS = {
    "rapid": ("rapid fire", "self"),
    "power": ("double score", "self"),
    "shield": ("shield", "self"),
    "slow": ("slow rivals", "rivals"),
    "weaken": ("weak fields", "rivals"),
    "drift": ("aim drift", "rivals"),
}


class Room:
    def __init__(self, code):
        import random

        self.code = code
        self.players = []
        self.phase = "lobby"
        self.round = 0
        self.match = 1
        self.seq = 0
        self.deadline = None
        self.updated = time.time()
        self.host = None
        self.live = None
        self.boosters = []
        self.notices = []
        self.next_booster = 6.0
        self.booster_index = 0
        self.random = random.Random(code)
        self.input_seq = {}
        self.last_tick_ms = 0.0

    def public(self):
        live = self.live.snapshot() if self.live else None
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
            "host": self.host,
            "server_time": time.time(),
            "live": live,
            "boosters": self.boosters,
            "notices": self.notices,
            "rules": {
                "rounds": ROUNDS,
                "setup_seconds": SETUP_SECONDS,
                "live_seconds": LIVE_SECONDS,
            },
        }

    def add(self, name, token=None):
        for p in self.players:
            if (
                isinstance(token, str)
                and token
                and token.isascii()
                and secrets.compare_digest(p["token"], token)
            ):
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
            "score": 0.0,
            "ready": False,
            "connected": True,
            "angle": 0.0,
            "generators": [],
            "effects": {},
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
        self.deadline = time.time() + SETUP_SECONDS
        self.live = None
        self.boosters = []
        self.notices = []
        self.next_booster = 6.0
        self.booster_index = 0
        self.input_seq = {}
        for i, p in enumerate(self.players):
            x, y = reactors(len(self.players))[i]
            p.update(
                ready=False,
                generators=[],
                angle=math.atan2(0.5 - y, 0.5 - x),
                effects={},
            )

    def launch(self):
        from .physics.streams import Streams

        self.live = Streams(len(self.players))
        self.phase = "simulation"
        self.deadline = time.time() + LIVE_SECONDS
        self.round_start_scores = [p["score"] for p in self.players]

    def spawn_booster(self):
        # Keep pickups away from reactors and one another. Cycle all six labels in a round.
        for _ in range(50):
            x = self.random.uniform(0.22, 0.78)
            y = self.random.uniform(0.14, 0.86)
            if all(
                math.hypot(x - cx, y - cy) > 0.15
                for cx, cy in reactors(len(self.players))
            ) and all(math.hypot(x - b["x"], y - b["y"]) > 0.13 for b in self.boosters):
                break
        kind = list(BOOSTERS)[(self.booster_index + self.round - 1) % len(BOOSTERS)]
        self.booster_index += 1
        label, target = BOOSTERS[kind]
        self.boosters.append(
            {
                "id": f"{self.match}-{self.round}-{self.booster_index}",
                "kind": kind,
                "label": label,
                "target": target,
                "x": x,
                "y": y,
                "expires": self.live.time + 10,
            }
        )

    def apply_booster(self, booster, owner):
        kind = booster["kind"]
        until = self.live.time + 6
        for i, p in enumerate(self.players):
            if (booster["target"] == "self" and i == owner) or (
                booster["target"] == "rivals" and i != owner
            ):
                p["effects"][kind] = until
        self.notices.append(
            {
                "text": f"{self.players[owner]['name']} · {booster['label']}",
                "until": self.live.time + 3,
            }
        )
        self.notices = self.notices[-3:]

    def advance(self):
        self.boosters = [b for b in self.boosters if b["expires"] > self.live.time]
        if self.live.time >= self.next_booster and len(self.boosters) < 2:
            self.spawn_booster()
            self.next_booster = self.live.time + 8
        picked = self.live.tick(self.players, self.boosters)
        for index, owner in picked:
            self.apply_booster(self.boosters[index], owner)
        taken = {i for i, _ in picked}
        self.boosters = [b for i, b in enumerate(self.boosters) if i not in taken]
        snap = self.live.snapshot()
        for i, p in enumerate(self.players):
            p["score"] = self.round_start_scores[i] + snap["scores"][i]
        self.notices = [n for n in self.notices if n["until"] > self.live.time]
        self.deadline = time.time() + max(0, LIVE_SECONDS - self.live.time)
        self.last_tick_ms = self.live.last_ms
        if self.live.time >= LIVE_SECONDS:
            self.phase = "results"
            self.deadline = time.time() + 4

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
                self.phase not in ("construction", "simulation")
                or data.get("round") != self.round
                or data.get("match") != self.match
            ):
                raise Invalid("this round is locked")
            seq = data.get("input_seq")
            if (
                isinstance(seq, bool)
                or not isinstance(seq, int)
                or seq < 0
                or seq <= self.input_seq.get(p["id"], -1)
            ):
                raise Invalid("stale controls")
            if action == "ready" and self.phase != "construction":
                raise Invalid("already live — keep aiming")
            angle, generators = validate_config(data, len(self.players))
            self.input_seq[p["id"]] = seq
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
                x["score"] = 0.0
            self.construct()
        else:
            raise Invalid("unknown action")
