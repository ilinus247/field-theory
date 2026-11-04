"""Shared, immutable arena fixtures; selected by the host before a match."""

ARENAS = {
    "open": {
        "id": "open",
        "name": "open field",
        "description": "An empty canvas. Your fields shape every route.",
        "objects": [],
    },
    "lenses": {
        "id": "lenses",
        "name": "lens garden",
        "description": "Two localized attraction wells draw streams into curved routes.",
        "objects": [
            {
                "kind": "lens",
                "label": "attraction lens",
                "x": 0.5,
                "y": 0.30,
                "radius": 0.075,
                "strength": 1.0,
            },
            {
                "kind": "lens",
                "label": "attraction lens",
                "x": 0.5,
                "y": 0.70,
                "radius": 0.075,
                "strength": 1.0,
            },
        ],
    },
    "eddies": {
        "id": "eddies",
        "name": "eddy court",
        "description": "Paired magnetic vortices turn streams in opposite directions without adding speed.",
        "objects": [
            {
                "kind": "vortex",
                "label": "clockwise eddy",
                "x": 0.5,
                "y": 0.30,
                "radius": 0.085,
                "strength": -1.0,
            },
            {
                "kind": "vortex",
                "label": "counterclockwise eddy",
                "x": 0.5,
                "y": 0.70,
                "radius": 0.085,
                "strength": 1.0,
            },
        ],
    },
}


def fixtures(arena):
    return ARENAS[arena]["objects"]
