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

- Public HTTPS frontend loads and the live JAX backend reports `jax-live-boris` with stream interactions enabled.
- Full public WSS smoke test **passed**: three actual 60-second rounds, 599 identical snapshots per round, live aiming and field placement/removal, labeled pickup spawning, sustained scoring, rematch, and same-identity reconnection. Total test duration: **203.9 seconds**, including results and connection/setup overhead.
- First test client's cumulative pressure scores after the three rounds: 55.04, 116.08, 171.29. Both clients received identical authoritative snapshots and scores.
- Two public browser tabs also exercised live aiming, placement, dragging, removal, owner labels, stronger streamlines, the rules modal, and visible pickup/effect labels. A harmful weak-fields effect was observed with its countdown.
- Production peak process memory was approximately **240 MB**, with observed live batches around **5–7 ms** per 100 ms simulation chunk. Two independent live rooms ran concurrently. Sampled CPU remained below Render's reported instance CPU allowance; these observations are not a sustained-load guarantee.
- GitHub CI passed for the live-stream source and frontend production build. Render remains on plan `free`, one instance, and the same public GitHub repository.

Reproduce using `python tests/live_smoke.py`.

## Not certified

Physical-phone hardware, phone portrait/landscape performance, sustained multi-room load, a forced Render idle-wake cycle, and independent VPN/network conditions remain unverified. Responsive pointer controls are implemented; the available browser inspection surface was 680 pixels wide.

## Hosting

Existing ChatGPT Sites frontend and Render Free backend are reused. No paid infrastructure, domains, databases, disks, or billing changes are part of this update. In-memory rooms are lost on deployment/restart. The GitHub repository remains public and MIT licensed.

## Network-delay regression fix

- Reproduced the prior defects: a 120-message delayed control burst generated 91 slowdown errors; a 300 ms outbound write delay marked a player disconnected, disabling their cannon.
- Added latest-input mailboxes on the server, bounded per-connection snapshot queues and a single writer, burst-tolerant flood protection, browser-side outbound backpressure, and connection-generation guards.
- Local suite: 27 backend tests and 3 client transport tests passed, plus the production build. Regression tests cover delayed input bursts, latest-state application, slow snapshot delivery with continued emission, bounded queues, replaced-socket close codes, client send cadence, and clearing obsolete controls.
- `tests/network_recovery.py` exercises a 120-message delayed burst followed by an entire minute of live controls over public WSS. Production execution passed after deployment: a 120-message delayed burst plus 741 ongoing controls over a full live minute, with 599 identical authoritative snapshots. Both players stayed connected, the cannon kept emitting, and there were no slowdown errors or firing interruptions. Total test duration was 61.1 seconds; production error logs were empty.

## Browser timer regression

The live browser reproduced `TypeError: Illegal invocation` in `ControlSender.arm` when moving the angle slider. Storing native browser timers as class members and invoking them as methods supplied an invalid receiver. This prevented control messages from being scheduled even though local controls rendered their new values. Timer wrappers now call the host functions normally. A receiver-sensitive regression test failed before the fix and passed afterward. Four client transport tests and the production build passed. The control panel now distinguishes server-confirmed controls from pending local changes.
