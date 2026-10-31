# FIELD THEORY

A minimalist, account-free multiplayer game of invisible forces. Arrange electric charges and magnetic coils, choose an angle, and let the Lorentz force decide the trajectory.

**Source:** https://github.com/ilinus247/field-theory  
**Public frontend:** https://field-theory.packedbasil2.chatgpt.site  
**Backend:** https://field-theory.onrender.com

![FIELD THEORY game interface](docs/screenshots/game.jpg)

## Play

Create a room with your display name, then share its five-letter code or URL with 1–3 friends. The host starts once two players are connected.

Each match has five rounds:

1. **Construct — 20 seconds:** place up to two generators, with at most one magnetic coil. Drag fields to move them, use their × buttons to remove them, and use the angle slider to aim. Protected reactor zones reject placement. Ready players launch early when everyone is ready.
2. **Simulate — 8 seconds:** every reactor launches one positive particle at fixed speed. All fields affect all particles. Configurations are locked.
3. **Results — 4 seconds:** each opposing reactor hit earns one point. A particle stops at its first reactor or boundary. Friendly hits earn nothing. Most points after five rounds wins; ties share victory. The host can start a rematch.

Red **+** repels; blue **−** attracts; violet **⊙** curves moving particles. Tap or click to place. Drag to adjust. Mouse and touch use the same controls. On phones, the controls appear below the arena.

## Architecture

- **Frontend:** React, TypeScript, Vite, and HTML Canvas. Canvas draws electric streamlines, coil rings, fading trails, and impact ripples. Streamlines represent the electric field; magnetic rings indicate coil locality rather than fictitious magnetic electric streamlines.
- **Backend:** Python, FastAPI, Uvicorn, and WebSockets; one process, independent in-memory rooms, no database or login.
- **Authority:** the server validates placement and angles, locks a round, computes trajectories once, and broadcasts the same frames and events to every client. A future server start timestamp and ping-based clock-offset estimate align playback. Clients interpolate, never score locally.
- **Protocol:** explicit phases, monotonically increasing state sequences, round IDs, per-room locks, bounded messages/rates, and random reconnection tokens. Refresh replaces the old socket without creating another player. Host ownership transfers to a connected player. Disconnected players do not block the construction timer.

Physics is separate from networking (`backend/app/physics`); rule validation lives in `game.py`; rendering lives in `frontend/src/Arena.tsx`.

## Physics

Normalized arena coordinates use gameplay units with q/m = 1:

```text
F = q(E + v × B)
Eᵢ(r) = kQᵢ(r − rᵢ) / (|r − rᵢ|² + ε²)^(3/2)
Bz(r) = B₀ exp(−|r − rc|² / (2σ²))
```

Parameters are centralized in `simulation.py`: dt = 1/240 s, ε = 0.065, k = 0.018, B₀ = 5, σ = 0.16, initial speed = 0.28, maximum speed = 1.4. Electric acceleration and aggregate magnetic field are bounded. The Boris update splits electric acceleration into two half-kicks around a norm-preserving magnetic velocity rotation. Position advances with the resulting velocity. This is a simplified game integrator, not a Maxwell solver. Swept segment-circle tests prevent fast particles tunneling through reactors. Trajectories are recorded at 30 Hz.

### JAX status

A local JAX 0.6.2 CPU JIT smoke test passed. The current game engine uses NumPy. No JAX game kernel is claimed: deployment reliability and the small four-particle workload take priority. NumPy keeps the dependency footprint small on Render's 512 MB free instance. A compiled JAX alternative remains a possible enhancement after production resource measurements; it is not needed for deterministic server-authoritative outcomes.

## Local development

Python 3.10+ (deployment targets 3.12), Node 22+, and npm are required.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

In a second terminal from the repository root:

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open http://localhost:5173. Use independent browser profiles/devices for independent players; tabs sharing local storage intentionally share a reconnect identity.

## Tests and production build

```sh
pip install pytest httpx
(cd backend && python -m pytest -q)
npm --prefix frontend run build
```

CI runs backend tests and the frontend production build. Tests cover field polarity, magnetic curvature and energy preservation, finite integration, determinism, swept collision detection, validation, room limits, stale rounds, independent rooms, five-round scoring/ties, rematches, malformed messages, and reconnect identity.

The network suite uses actual FastAPI WebSocket sessions through TestClient; it is separate from browser interaction checks. It accelerates simulation/results deadlines to avoid waiting through each playback. It does not by itself prove public WSS connectivity or real-device mobile behavior.

## Deployment

The requested frontend publisher is **ChatGPT Sites**. `.openai/hosting.json` points to the generated `dist` static build. Build with the public backend URL before packaging. Sites source synchronization uses its own provider repository; the public GitHub repository contains the same application source.

The backend is configured by `render.yaml`: **Free** web service, one Uvicorn worker, port supplied by Render, `/health` health check, no database or disks. Import the public GitHub repository in Render and explicitly verify the free plan before deployment. `ALLOWED_ORIGINS` must include the exact public frontend origin. Never enable paid upgrades or add payment details for this project.

A `vercel.json` configuration is also supplied if Vercel Hobby is used as an alternative frontend host. It must import this personal GitHub repository and set `VITE_BACKEND_URL` before building.

### Environment variables

| Variable | Where | Meaning |
|---|---|---|
| `VITE_BACKEND_URL` | frontend build | Public HTTPS backend origin; defaults to localhost:8000 for development |
| `ALLOWED_ORIGINS` | backend | Comma-separated allowed frontend origins, without trailing slashes |
| `PORT` | backend | Host-provided listening port |

See `.env.example`. No API keys are required by the game. Hosting/repository credentials belong in platform settings, never source code.

## Limits and operations

Render Free has limited CPU/RAM, shared monthly allowances, idle spin-down, and approximately one-minute cold starts. The frontend displays connection state and retries automatically. Rooms disappear after restart, redeployment, or spin-down. An expired room code requires a new room. This MVP caps active rooms at 64 and room size at four. Empty rooms expire after five minutes. No persistence, spectators, projectile collisions, sound, or trajectory previews are included.

A single browser origin stores one active player identity. Do not share its reconnection token. Anyone with a room code can join an unstarted room. Rate limits are per socket; this is hobby-scale abuse resistance, not a hardened tournament service.

## License

MIT. Copyright © 2026 ilinus247. See [LICENSE](LICENSE).
