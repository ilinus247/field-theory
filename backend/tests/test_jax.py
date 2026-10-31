import numpy as np
from app.physics.jax_engine import step, kernel, arrays, simulate_jax
from app.physics.simulation import simulate_numpy


def test_jax_matches_reference_and_deterministic():
    players = [
        dict(
            id="a",
            angle=0.1,
            generators=[
                dict(kind="positive", x=0.4, y=0.4),
                dict(kind="coil", x=0.5, y=0.5),
            ],
        ),
        dict(id="b", angle=3.2, generators=[dict(kind="negative", x=0.7, y=0.3)]),
    ]
    a = simulate_jax(players)
    b = simulate_numpy(players)
    assert a == simulate_jax(players)
    assert len(a["frames"]) == len(b["frames"])
    for af, bf in zip(a["frames"], b["frames"]):
        for ap, bp in zip(af, bf):
            assert (ap is None) == (bp is None)
            if ap is not None:
                np.testing.assert_allclose(ap, bp, atol=1e-11)
    assert [(e["owner"], e["target"], e["time"]) for e in a["events"]] == [
        (e["owner"], e["target"], e["time"]) for e in b["events"]
    ]


def test_jax_magnetic_energy():
    players = [
        dict(id="a", angle=0, generators=[dict(kind="coil", x=0.5, y=0.5)]),
        dict(id="b", angle=3.14, generators=[]),
    ]
    p, v, s, c, a = arrays(players)
    # Full trajectory also tests the actual compiled scan and masked inactive slots.
    positions, alive, targets, ends, velocities = map(np.asarray, kernel(p, v, s, c, a))
    np.testing.assert_allclose(
        np.linalg.norm(velocities[:, :2], axis=2), 0.28, atol=1e-11
    )
    assert np.isfinite(positions).all()


def test_jax_polarity_and_swept_collision():
    import jax.numpy as jnp

    p = jnp.array([[0.7, 0.5]] * 4)
    v = jnp.zeros((4, 2))
    s = jnp.zeros((8, 4)).at[0].set(jnp.array([0.5, 0.5, 1.0, 0.0]))
    _, repel = step(p, v, s)
    _, attract = step(p, v, s.at[0, 2].set(-1))
    assert repel[0, 0] > 0 and attract[0, 0] < 0
    players = [
        dict(id="a", angle=0, generators=[]),
        dict(id="b", angle=3.14, generators=[]),
    ]
    p, v, s, c, a = arrays(players)
    p = p.at[0].set(jnp.array([0.8, 0.5]))
    v = v.at[0].set(jnp.array([40.0, 0.0]))
    # Step caps velocity at 1.4, so start just outside target and cross its edge in one tick.
    p = p.at[0].set(jnp.array([0.847, 0.5]))
    output = kernel(p, v, s, c, a)
    assert int(output[2][0, 0]) == 1


def test_three_and_four_player_slots_and_balanced_triangle():
    from app.physics.simulation import reactors

    for count in (3, 4):
        players = [dict(id=str(i), angle=i * 1.5, generators=[]) for i in range(count)]
        result = simulate_jax(players)
        assert len(result["frames"]) == 241
        assert all(len(frame) == count for frame in result["frames"])
        assert all(
            e["owner"] in {str(i) for i in range(count)} for e in result["events"]
        )
    cs = np.array(reactors(3))
    distances = [np.linalg.norm(cs[i] - cs[(i + 1) % 3]) for i in range(3)]
    np.testing.assert_allclose(distances, distances[0], atol=1e-12)
