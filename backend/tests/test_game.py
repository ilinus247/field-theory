import math
import pytest
from app.game import Room, Invalid, validate_config


def test_validation():
    for config in [
        dict(angle=float("nan"), generators=[]),
        dict(angle=0, generators=[dict(kind="positive", x=0.12, y=0.5)]),
        dict(angle=0, generators=[dict(kind="coil", x=0.5, y=0.5)] * 2),
        dict(angle=0, generators=[dict(kind="positive", x=-1, y=0.5)]),
    ]:
        with pytest.raises(Invalid):
            validate_config(config, 2)
    assert validate_config(dict(angle=0, generators=[]), 2) == (0, [])


def test_room_and_stale_round():
    r = Room("ABCDE")
    a = r.add("ada")
    b = r.add("ben")
    assert r.add("ada", a["token"]) is a
    r.action(a, {"type": "start"})
    assert r.round == 1 and r.phase == "construction"
    with pytest.raises(Invalid):
        r.action(
            b, dict(type="ready", input_seq=1, match=1, round=0, angle=0, generators=[])
        )
    r.action(
        b,
        dict(type="ready", input_seq=1, match=1, round=1, angle=math.pi, generators=[]),
    )
    assert b["ready"]
    assert "token" not in str(r.public())
    r.phase = "finished"
    r.round = 3
    a["score"] = 3
    r.action(a, {"type": "rematch"})
    assert r.round == 1 and a["score"] == 0


def test_limits_and_host():
    r = Room("ABCDE")
    p = r.add("a")
    with pytest.raises(Invalid):
        r.action(p, {"type": "start"})
    for name in ["b", "c", "d"]:
        r.add(name)
    with pytest.raises(Invalid):
        r.add("e")
    with pytest.raises(Invalid):
        r.action(r.players[1], {"type": "start"})


def test_previous_match_cannot_overwrite_rematch():
    r = Room("ABCDE")
    a = r.add("a")
    r.add("b")
    r.action(a, {"type": "start"})
    r.phase = "finished"
    r.action(a, {"type": "rematch"})
    assert r.match == 2 and r.round == 1
    with pytest.raises(Invalid):
        r.action(
            a, dict(type="ready", input_seq=1, match=1, round=1, angle=0, generators=[])
        )
    assert not a["ready"]
    r.action(
        a, dict(type="ready", input_seq=1, match=2, round=1, angle=0, generators=[])
    )
    assert a["ready"]
