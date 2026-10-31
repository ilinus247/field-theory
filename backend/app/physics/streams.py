"""Authoritative live JAX streams: 128 fixed slots, Boris steps, pairwise repulsion."""

import os

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import jax

jax.config.update("jax_enable_x64", True)
import jax.numpy as j
import numpy as np
from .simulation import reactors, SOFTENING, ELECTRIC_K, MAGNETIC_B, MAGNETIC_SIGMA

DT = 1 / 120
SUBSTEPS = 12
CHUNK = DT * SUBSTEPS
SLOTS = 32
CAPACITY = 128
LIFETIME = 3.0
CONTACT_WINDOW = 0.23
PAIR_K = 0.000035
OWNERS = j.repeat(j.arange(4), SLOTS)


def electric_at(p, sources):
    d = p - sources[:, :2]
    r2 = j.sum(d * d, axis=1)
    e = j.sum(
        ELECTRIC_K * sources[:, 2, None] * d / (r2[:, None] + SOFTENING**2) ** 1.5,
        axis=0,
    )
    b = j.sum(MAGNETIC_B * sources[:, 3] * j.exp(-r2 / (2 * MAGNETIC_SIGMA**2)))
    return e, j.clip(b, -20, 20)


def turn(v):
    return j.stack([v[:, 1], -v[:, 0]], axis=1)


@jax.jit
def forces(positions, ttl, sources, interaction):
    e, b = jax.vmap(electric_at, in_axes=(0, None))(positions, sources)
    d = positions[:, None, :] - positions[None, :, :]
    r2 = j.sum(d * d, axis=2)
    mask = (
        (ttl[:, None] > 0) & (ttl[None, :] > 0) & (OWNERS[:, None] != OWNERS[None, :])
    )
    pair = j.sum(
        PAIR_K * d / (r2[:, :, None] + 0.025**2) ** 1.5 * mask[:, :, None], axis=1
    )
    e += pair * interaction
    e *= j.minimum(1.0, 3.0 / j.maximum(j.linalg.norm(e, axis=1, keepdims=True), 1e-20))
    return e, b


def segment_dist(a, b, centers):
    d = b - a
    length = j.sum(d * d, axis=1)
    t = j.clip(
        j.sum((centers[None, :, :] - a[:, None, :]) * d[:, None, :], axis=2)
        / j.maximum(length[:, None], 1e-20),
        0,
        1,
    )
    return j.linalg.norm(
        a[:, None, :] + t[:, :, None] * d[:, None, :] - centers[None, :, :], axis=2
    )


@jax.jit
def advance(
    state,
    sources,
    centers,
    connected,
    angles,
    intervals,
    power,
    shield,
    boosters,
    boost_active,
    interaction,
):
    """Run 0.1s as twelve compiled steps; controls stay constant within this chunk."""

    def sub(carry, _):
        p, v, ttl, cursors, cooldown, contact, scores, bactive, pickers = carry
        spawn = (cooldown <= 1e-8) & connected
        idx = j.arange(4) * SLOTS + cursors
        direction = j.stack([j.cos(angles), j.sin(angles)], axis=1)
        p = p.at[idx].set(j.where(spawn[:, None], centers + direction * 0.046, p[idx]))
        v = v.at[idx].set(j.where(spawn[:, None], direction * 0.42, v[idx]))
        ttl = ttl.at[idx].set(j.where(spawn, LIFETIME, ttl[idx]))
        cursors = (cursors + spawn.astype(j.int32)) % SLOTS
        cooldown = j.where(spawn, intervals, cooldown) - DT
        e, b = forces(p, ttl, sources, interaction)
        minus = v + e * DT / 2
        t = b[:, None] * DT / 2
        s = 2 * t / (1 + t * t)
        nv = minus + turn(minus + turn(minus) * t) * s + e * DT / 2
        nv *= j.minimum(
            1.0, 1.4 / j.maximum(j.linalg.norm(nv, axis=1, keepdims=True), 1e-20)
        )
        np_ = p + nv * DT
        alive = ttl > 0
        rhit = (
            (segment_dist(p, np_, centers) < 0.031)
            & (centers[:, 0] >= 0)[None, :]
            & alive[:, None]
        )
        # Disconnected reactors still occupy space, but cannot emit or earn points.
        bhit = (
            (segment_dist(p, np_, boosters) < 0.035) & bactive[None, :] & alive[:, None]
        )
        picked = j.any(bhit, axis=0)
        picker = (
            j.argmin(j.where(bhit, j.arange(CAPACITY)[:, None], CAPACITY), axis=0)
            // SLOTS
        )
        pickers = j.where(picked & (pickers < 0), picker.astype(j.int32), pickers)
        bactive = bactive & ~picked
        hitmatrix = j.any(rhit.reshape((4, SLOTS, 4)), axis=1) & ~j.eye(4, dtype=bool)
        contact = j.where(hitmatrix, CONTACT_WINDOW, j.maximum(0, contact - DT))
        scoring = (
            (contact > 0)
            & ~j.eye(4, dtype=bool)
            & connected[:, None]
            & connected[None, :]
            & ~shield[None, :]
        )
        scores += j.sum(scoring, axis=1) * power * DT
        dead = (
            j.any(rhit, axis=1)
            | j.any(bhit, axis=1)
            | j.any((np_ < 0) | (np_ > 1), axis=1)
        )
        ttl = j.where(dead, 0, j.maximum(0, ttl - DT))
        p = j.where(alive[:, None], np_, p)
        v = j.where(alive[:, None], nv, v)
        return (p, v, ttl, cursors, cooldown, contact, scores, bactive, pickers), None

    extra = (boost_active, j.full((2,), -1, dtype=j.int32))
    result, _ = jax.lax.scan(sub, (*state, *extra), None, length=SUBSTEPS)
    return result[:7], result[7], result[8]


class Streams:
    def __init__(self, count, interactions=True):
        self.count = count
        self.time = 0.0
        self.interactions = interactions
        self.centers = np.full((4, 2), -10.0)
        self.centers[:count] = reactors(count)
        self.state = (
            j.zeros((CAPACITY, 2)),
            j.zeros((CAPACITY, 2)),
            j.zeros(CAPACITY),
            j.zeros(4, dtype=j.int32),
            j.zeros(4),
            j.zeros((4, 4)),
            j.zeros(4),
        )
        self.last_ms = 0.0

    def tick(self, players, boosters):
        import time

        started = time.perf_counter()
        sources = np.zeros((8, 4))
        angles = np.zeros(4)
        intervals = np.full(4, 0.2)
        power = np.ones(4)
        shield = np.zeros(4, dtype=bool)
        connected = np.zeros(4, dtype=bool)
        n = 0
        for i, p in enumerate(players):
            fx = p.get("effects", {})
            on = lambda key: fx.get(key, 0) > self.time
            connected[i] = p.get("connected", True)
            angles[i] = p["angle"] + (
                0.14 * np.sin(self.time * 5 + i) if on("drift") else 0
            )
            intervals[i] = (0.1 if on("rapid") else 0.2) * (2 if on("slow") else 1)
            power[i] = 2 if on("power") else 1
            shield[i] = on("shield")
            strength = 0.45 if on("weaken") else 1
            for g in p["generators"]:
                sources[n] = [
                    g["x"],
                    g["y"],
                    strength
                    * (
                        1
                        if g["kind"] == "positive"
                        else -1 if g["kind"] == "negative" else 0
                    ),
                    strength * (g["kind"] == "coil"),
                ]
                n += 1
        bpos = np.full((2, 2), -10.0)
        ba = np.zeros(2, dtype=bool)
        for i, b in enumerate(boosters):
            bpos[i] = [b["x"], b["y"]]
            ba[i] = True
        self.state, _, picked = advance(
            self.state,
            j.asarray(sources),
            j.asarray(self.centers),
            j.asarray(connected),
            j.asarray(angles),
            j.asarray(intervals),
            j.asarray(power),
            j.asarray(shield),
            j.asarray(bpos),
            j.asarray(ba),
            j.asarray(float(self.interactions)),
        )
        picked = np.asarray(picked)
        self.time = round(self.time + CHUNK, 6)
        self.last_ms = (time.perf_counter() - started) * 1000
        return [
            (i, int(owner))
            for i, owner in enumerate(picked[: len(boosters)])
            if owner >= 0
        ]

    def snapshot(self):
        p, v, ttl, _, _, contact, scores = map(np.asarray, self.state)
        particles = [
            [
                int(slot),
                int(slot // SLOTS),
                round(float(p[slot, 0]), 5),
                round(float(p[slot, 1]), 5),
            ]
            for slot in np.flatnonzero(ttl > 0)
        ]
        return {
            "time": self.time,
            "particles": particles,
            "contact": (contact[: self.count, : self.count] > 0).tolist(),
            "scores": scores[: self.count].tolist(),
            "interactions": self.interactions,
        }
