"""Fixed-shape CPU JAX engine. One compiled scan handles 2–4 players / 8 fields."""

import os

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import jax

jax.config.update("jax_enable_x64", True)
import jax.numpy as jnp
import numpy as np
from .simulation import (
    DT,
    DURATION,
    SOFTENING,
    ELECTRIC_K,
    MAGNETIC_B,
    MAGNETIC_SIGMA,
    SPEED,
    MAX_SPEED,
    REACTOR_RADIUS,
    reactors,
)


def field(position, sources):
    delta = position - sources[:, :2]
    r2 = jnp.sum(delta * delta, axis=1)
    electric = jnp.sum(
        ELECTRIC_K * sources[:, 2, None] * delta / (r2[:, None] + SOFTENING**2) ** 1.5,
        axis=0,
    )
    electric *= jnp.minimum(1.0, 3.0 / jnp.maximum(jnp.linalg.norm(electric), 1e-30))
    magnetic = jnp.clip(
        jnp.sum(MAGNETIC_B * sources[:, 3] * jnp.exp(-r2 / (2 * MAGNETIC_SIGMA**2))),
        -20,
        20,
    )
    return electric, magnetic


def rotate(v):
    return jnp.stack([v[..., 1], -v[..., 0]], axis=-1)


@jax.jit
def step(positions, velocities, sources):
    electric, magnetic = jax.vmap(field, in_axes=(0, None))(positions, sources)
    minus = velocities + electric * DT / 2
    t = magnetic[:, None] * DT / 2
    s = 2 * t / (1 + t * t)
    prime = minus + rotate(minus) * t
    velocity = minus + rotate(prime) * s + electric * DT / 2
    velocity *= jnp.minimum(
        1.0,
        MAX_SPEED
        / jnp.maximum(jnp.linalg.norm(velocity, axis=1, keepdims=True), 1e-30),
    )
    return positions + velocity * DT, velocity


@jax.jit
def kernel(positions, velocities, sources, centers, active):
    def advance(carry, _):
        p, v, alive = carry
        newp, newv = step(p, v, sources)
        delta = newp - p
        length = jnp.sum(delta * delta, axis=1)
        tocenter = centers[None, :, :] - p[:, None, :]
        fraction = jnp.clip(
            jnp.sum(tocenter * delta[:, None, :], axis=2)
            / jnp.maximum(length[:, None], 1e-30),
            0,
            1,
        )
        nearest = p[:, None, :] + fraction[:, :, None] * delta[:, None, :]
        distance = jnp.linalg.norm(nearest - centers[None, :, :], axis=2)
        hits = (distance <= REACTOR_RADIUS) & active[None, :] & alive[:, None]
        # Match the reference's nearest-center ordering when several circles intersect a segment.
        hit_order = jnp.where(hits, jnp.linalg.norm(tocenter, axis=2), jnp.inf)
        target = jnp.where(jnp.any(hits, axis=1), jnp.argmin(hit_order, axis=1), -1)
        outside = jnp.any((newp < 0) | (newp > 1), axis=1)
        nextalive = alive & (target < 0) & ~outside
        nextp = jnp.where(alive[:, None], newp, p)
        nextv = jnp.where(alive[:, None], newv, v)
        return (nextp, nextv, nextalive), (p, alive, target, nextp, nextv)

    return jax.lax.scan(
        advance, (positions, velocities, active), None, length=int(DURATION / DT) + 1
    )[1]


def arrays(players):
    count = len(players)
    centers = np.zeros((4, 2))
    centers[:count] = reactors(count)
    positions = np.zeros((4, 2))
    velocities = np.zeros((4, 2))
    sources = np.zeros((8, 4))
    active = np.arange(4) < count
    index = 0
    for i, p in enumerate(players):
        direction = np.array([np.cos(p["angle"]), np.sin(p["angle"])])
        positions[i] = centers[i] + direction * 0.046
        velocities[i] = direction * SPEED
        for g in p["generators"]:
            sources[index] = [
                g["x"],
                g["y"],
                1 if g["kind"] == "positive" else -1 if g["kind"] == "negative" else 0,
                1 if g["kind"] == "coil" else 0,
            ]
            index += 1
    return tuple(
        jnp.asarray(a) for a in (positions, velocities, sources, centers, active)
    )


def simulate_jax(players):
    positions, alive, targets, ends, _ = map(np.asarray, kernel(*arrays(players)))
    frames = [
        [positions[t, i].tolist() if alive[t, i] else None for i in range(len(players))]
        for t in range(0, len(positions), 8)
    ]
    events = []
    for t, i in np.argwhere(targets >= 0):
        j = int(targets[t, i])
        events.append(
            {
                "owner": players[i]["id"],
                "target": players[j]["id"],
                "scored": int(i) != j,
                "time": int(t) * DT,
                "x": float(ends[t, i, 0]),
                "y": float(ends[t, i, 1]),
            }
        )
    return {
        "frames": frames,
        "events": events,
        "frame_dt": 8 * DT,
        "duration": DURATION,
    }
