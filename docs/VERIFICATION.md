# Verification record — live streams update

October 31, 2026. This release replaces prerecorded eight-second playback with live JAX-authoritative streams.

## Executed locally

- 22 automated tests passed, including the new streaming kernel and WebSocket match loop.
- TypeScript compilation and Vite production build passed.
- JAX four-player benchmark with rapid fire, eight generators, and inter-stream repulsion: approximately 2 ms per 100 ms simulation batch and 190 MB peak process memory on the development machine. Production timing is a separate check.
- Physics checks include rival-stream repulsion, magnetic-only energy preservation within 1e-11, finite deterministic bounded emission, swept reactor/pickup collisions, contact scoring, shields, double score, and all six booster target/expiry rules.
- Networking checks include identical sequenced snapshots, three-round completion, rematches, refresh identity, invalid room codes, independent rooms, malformed input, and stale input/match/round rejection. Unit network tests accelerate round endings; they do not claim to wait through real minutes.
- Browser: rules popup opens and shows the live rules; two independent tabs create/join a room; automatic continuous fire renders; generators can be placed and dragged during live play; stronger field lines and owner labels render; labeled pickups appear.

## Production checks

The previous release was verified over public HTTPS/WSS. The live-stream release requires its own public smoke test after deployment. Run `python tests/live_smoke.py` for three full 60-second rounds with matching snapshots, live placement/removal, scoring, pickup spawning, rematch, and reconnect checks.

## Not certified

Physical-phone hardware, phone portrait/landscape performance, sustained multi-room load, a forced Render idle-wake cycle, and independent VPN/network conditions remain unverified. Responsive pointer controls are implemented; the available browser inspection surface was 680 pixels wide.

## Hosting

Existing ChatGPT Sites frontend and Render Free backend are reused. No paid infrastructure, domains, databases, disks, or billing changes are part of this update. In-memory rooms are lost on deployment/restart. The GitHub repository remains public and MIT licensed.
