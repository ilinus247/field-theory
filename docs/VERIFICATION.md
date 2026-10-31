# Verification record

Executed October 31, 2026. Reported checks are observations, not guarantees of future availability.

## Passed

- Backend automated suite: **15 tests passed**; physics, validation, WebSocket room/match progression, stale and malformed messages, reconnect identity, independent rooms, five-round ties, and rematches.
- JAX CPU tests: electric polarity; magnetic curvature; magnetic-only speed conserved within 1e-11; finite trajectories; deterministic repeat runs; agreement with NumPy reference within 1e-11 for tested trajectories; swept reactor collision; 2–4 player output shapes.
- TypeScript compilation and Vite production build.
- GitHub Actions on Linux/Python 3.12, including JAX and the frontend build.
- Anonymous HTTPS frontend access without login.
- Live Render `/health` reports `jax-boris`. Observed physics initialization: 8.0 seconds. Observed peak process memory: 224.9 MB. Render sampled memory during gameplay: approximately 142 MB, below the 512 MB Free limit.
- Real production WSS test: two clients completed all five rounds, received identical authoritative playback and scores, tied 5–5, started a rematch, and reconnected with the same player identity. Duration: 79.1 seconds. Reproducible using `python tests/live_smoke.py`.
- Two independent public browser tabs: create/join, synchronized roster/ready, charge placement/dragging, magnetic coil placement, launch, and curved trajectory rendering.
- Local browser observation: construction advances without every player pressing Ready.
- Public personal GitHub repository; MIT License recognized by GitHub; application source, tests, deployment configuration, and screenshots pushed.
- Source review/search found no committed credentials. Player tokens are runtime-generated and excluded from public state. Public backend URL is intentionally non-secret.
- Render service explicitly created with plan `free`, one instance, no database or persistent disk. No paid resources, domains, or upgrades were provisioned.

## Not fully verified

- Physical phones, real touch hardware, and phone portrait/landscape performance. Pointer controls and responsive CSS are implemented. Browser layout was inspected at the available 680-pixel width; the viewport override did not change the actual size.
- A full idle spin-down/wake cycle on Render. Reconnection and wake-state messaging are implemented; the actual cold idle cycle was not forced.
- Independent consumer-network/VPN tests or sustained load/abuse testing.
- Exhaustive numerical accuracy across every possible field configuration. These are bounded gameplay approximations, not a full physical solver.

## Hosting constraints

Render Free sleeps after inactivity; wake-up can take about a minute. All room state is in memory and disappears after restart or redeploy. Monthly quotas apply. No payment information was entered or billing settings changed. Existing account billing configuration and future overage behavior were not independently audited.

Sites publication uses its managed source mirror. GitHub remains the public MIT source of record. Render deploys the GitHub `main` branch. Automatic deployment is configured, but push-triggered deployment was not observed for the public-URL repository import; release deployment was reconciled explicitly. The README documents environment variables and local reproduction.
