import math
import numpy as np
import jax.numpy as j
import pytest
from app.arenas import ARENAS
from app.game import Room, Invalid, validate_config
from app.physics.streams import (
    Streams,
    arena_fields,
    electric_at,
    MAGNETIC_B,
    MAGNETIC_SIGMA,
)
from test_streams import players, inject


def test_host_selection_locked_through_all_rounds_and_changeable_before_rematch():
    r = Room("ARENA")
    a, b = r.add("a"), r.add("b")
    with pytest.raises(Invalid):
        r.action(b, {"type": "arena", "arena": "lenses"})
    with pytest.raises(Invalid):
        r.action(a, {"type": "arena", "arena": "unknown"})
    r.action(a, {"type": "arena", "arena": "lenses"})
    assert r.public()["arena"] == ARENAS["lenses"]
    r.action(a, {"type": "start"})
    for _ in range(3):
        with pytest.raises(Invalid):
            r.action(a, {"type": "arena", "arena": "eddies"})
        assert r.arena == "lenses"
        r.construct()
    r.phase = "finished"
    r.action(a, {"type": "arena", "arena": "eddies"})
    r.action(a, {"type": "rematch"})
    assert r.arena == "eddies" and r.round == 1


def test_fixed_objects_reject_overlapping_fields_and_pickups():
    for arena in ("lenses", "eddies"):
        with pytest.raises(Invalid, match="arena objects"):
            validate_config(
                dict(angle=0, generators=[dict(kind="coil", x=0.5, y=0.3)]), 2, arena
            )
        r = Room("ARENA")
        r.add("a")
        r.add("b")
        r.arena = arena
        r.construct()
        r.launch()
        for _ in range(30):
            r.boosters = []
            r.spawn_booster()
            b = r.boosters[0]
            assert all(
                math.hypot(b["x"] - o["x"], b["y"] - o["y"]) > o["radius"] + 0.06
                for o in ARENAS[arena]["objects"]
            )


def test_lens_attracts_locally_and_open_has_no_force():
    s = Streams(2, False, "lenses")
    e, b = arena_fields(
        j.array([[0.55, 0.3], [0.45, 0.3], [0.95, 0.3]]), s.arena_objects
    )
    assert e[0, 0] < 0 < e[1, 0]
    assert abs(e[2, 0]) < 0.00001
    np.testing.assert_allclose(b, 0)
    e, b = arena_fields(j.array([[0.5, 0.3]]), Streams(2).arena_objects)
    np.testing.assert_allclose(e, 0)
    np.testing.assert_allclose(b, 0)


def test_eddies_opposite_rotation_conserve_energy_and_deterministic():
    a, b = Streams(2, False, "eddies"), Streams(2, False, "eddies")
    ps = players()
    for p in ps:
        p["connected"] = False
    for s in (a, b):
        inject(s, [0.5, 0.3], (0.2, 0))
    _, bz = arena_fields(j.array([[0.5, 0.3], [0.5, 0.7]]), a.arena_objects)
    assert bz[0] < 0 < bz[1]
    for _ in range(10):
        a.tick(ps, [])
        b.tick(ps, [])
    assert a.snapshot() == b.snapshot()
    assert np.linalg.norm(np.asarray(a.state[1])[0]) == pytest.approx(0.2, abs=1e-11)
    assert np.isfinite(np.asarray(a.state[0])).all()


def test_curve_nerf_still_bends_but_does_not_reverse_a_center_crossing():
    assert MAGNETIC_B == 2.5 and MAGNETIC_SIGMA == 0.11
    s = Streams(2, False)
    ps = players()
    for p in ps:
        p["connected"] = False
    ps[0]["generators"] = [dict(kind="coil", x=0.5, y=0.5)]
    inject(s, [0.3, 0.5], (0.42, 0))
    for _ in range(8):
        s.tick(ps, [])
    v = np.asarray(s.state[1])[0]
    assert v[0] > 0 and v[1] < -0.1
    assert np.linalg.norm(v) == pytest.approx(0.42, abs=1e-11)
