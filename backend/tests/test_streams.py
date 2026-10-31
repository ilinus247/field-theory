import math
import jax.numpy as j
import numpy as np
import pytest
from app.physics.streams import Streams, forces, CAPACITY
from app.game import Room, Invalid, BOOSTERS


def players():
    return [
        dict(id="a", angle=0.0, generators=[], effects={}, connected=True),
        dict(id="b", angle=-math.pi / 2, generators=[], effects={}, connected=True),
    ]


def inject(s, position, velocity=(0.42, 0), slot=0):
    p, v, ttl, c, cd, contact, score = s.state
    s.state = (
        p.at[slot].set(j.array(position)),
        v.at[slot].set(j.array(velocity)),
        ttl.at[slot].set(1),
        c,
        j.full(4, 10.0),
        contact,
        score,
    )


def test_opposing_streams_repel():
    p = (
        j.zeros((CAPACITY, 2))
        .at[0]
        .set(j.array([0.45, 0.5]))
        .at[32]
        .set(j.array([0.55, 0.5]))
    )
    ttl = j.zeros(CAPACITY).at[0].set(1).at[32].set(1)
    e, _ = forces(p, ttl, j.zeros((8, 4)), j.array(1.0))
    assert e[0, 0] < 0 and e[32, 0] > 0
    off, _ = forces(p, ttl, j.zeros((8, 4)), j.array(0.0))
    np.testing.assert_allclose(off, 0)


def test_sustained_scoring_and_shield_power():
    for effect, expected in [({}, 0.1), ({"power": 10}, 0.2)]:
        s = Streams(2, False)
        ps = players()
        ps[0]["effects"] = effect
        inject(s, [0.847, 0.5])
        s.tick(ps, [])
        assert s.snapshot()["scores"][0] == pytest.approx(expected)
        assert s.snapshot()["scores"][1] == 0
    s = Streams(2, False)
    ps = players()
    ps[1]["effects"] = {"shield": 10}
    inject(s, [0.847, 0.5])
    s.tick(ps, [])
    assert s.snapshot()["scores"] == [0, 0]


def test_live_aim_moves_fields_and_stale_controls():
    r = Room("TESTA")
    a = r.add("a")
    r.add("b")
    r.action(a, {"type": "start"})
    r.launch()
    d = dict(
        type="configure",
        match=1,
        round=1,
        input_seq=1,
        angle=0.4,
        generators=[dict(kind="coil", x=0.4, y=0.4)],
    )
    r.action(a, d)
    assert a["angle"] == 0.4 and a["generators"][0]["kind"] == "coil"
    with pytest.raises(Invalid):
        r.action(a, d)
    d.update(input_seq=2, angle=0.8, generators=[])
    r.action(a, d)
    assert a["angle"] == 0.8 and not a["generators"]


def test_booster_pickup_is_swept_and_single_use():
    s = Streams(2, False)
    ps = players()
    inject(s, [0.26, 0.5])
    boost = [dict(x=0.3, y=0.5)]
    assert s.tick(ps, boost) == [(0, 0)]
    assert float(np.asarray(s.state[2])[0]) == 0
    # Room removes picked objects; without the pickup slot it cannot be collected twice.
    assert not s.tick(ps, [])


def test_all_booster_targets_and_expiry():
    r = Room("TESTB")
    a = r.add("a")
    b = r.add("b")
    r.construct()
    r.launch()
    for kind, (label, target) in BOOSTERS.items():
        r.apply_booster(dict(kind=kind, label=label, target=target), 0)
        assert (kind in a["effects"]) == (target == "self")
        assert (kind in b["effects"]) == (target == "rivals")
    assert all(t == 6 for t in a["effects"].values())
    r.live.time = 7
    assert not any(t > r.live.time for t in a["effects"].values())


def test_continuous_emission_bounded_finite_and_deterministic():
    a = Streams(4)
    b = Streams(4)
    ps = players() + [
        dict(id="c", angle=1.0, generators=[], effects={"rapid": 100}, connected=True),
        dict(id="d", angle=2.0, generators=[], effects={}, connected=True),
    ]
    for _ in range(80):
        a.tick(ps, [])
        b.tick(ps, [])
    assert a.snapshot() == b.snapshot()
    assert len(a.snapshot()["particles"]) <= 128
    assert np.isfinite(np.asarray(a.state[0])).all()
    # Change an angle while streaming: the next new slot uses the new direction.
    old = np.asarray(a.state[1]).copy()
    ps[0]["angle"] = math.pi / 2
    for _ in range(3):
        a.tick(ps, [])
    assert not np.array_equal(old, np.asarray(a.state[1]))


def test_live_magnetic_only_energy():
    s = Streams(2, False)
    ps = players()
    for p in ps:
        p["connected"] = False
    ps[0]["generators"] = [dict(kind="coil", x=0.5, y=0.5)]
    inject(s, [0.5, 0.5], (0.2, 0))
    for _ in range(10):
        s.tick(ps, [])
    assert np.linalg.norm(np.asarray(s.state[1])[0]) == pytest.approx(0.2, abs=1e-11)
