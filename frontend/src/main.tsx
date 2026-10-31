import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Arena } from "./Arena";
import { Rules } from "./Rules";
import { colors, effectNames, type State, type Generator } from "./types";
import "./style.css";
const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
function App() {
  const [state, setState] = useState<State | null>(null),
    [name, setName] = useState(localStorage.getItem("ft-name") || ""),
    [code, setCode] = useState(
      new URLSearchParams(location.search).get("room") || "",
    ),
    [me, setMe] = useState(""),
    [status, setStatus] = useState("not connected"),
    [error, setError] = useState(""),
    [kind, setKind] = useState<Generator["kind"]>("positive"),
    [generators, setGenerators] = useState<Generator[]>([]),
    [angle, setAngle] = useState(0),
    [mode, setMode] = useState<"place" | "aim">("aim"),
    [offset, setOffset] = useState(0),
    [now, setNow] = useState(Date.now()),
    [copied, setCopied] = useState(false),
    [rules, setRules] = useState(false);
  const ws = useRef<WebSocket | null>(null),
    intent = useRef<any>(null),
    retry = useRef<ReturnType<typeof setTimeout> | null>(null),
    configTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    queued = useRef<any>(null),
    sequence = useRef(-1),
    inputSeq = useRef(Date.now() * 1000),
    current = useRef<State | null>(null),
    angleRef = useRef(angle),
    genRef = useRef(generators),
    playerId = useRef("");
  current.current = state;
  angleRef.current = angle;
  genRef.current = generators;
  const send = (data: any) => {
    if (["configure", "ready"].includes(data.type))
      data = { ...data, input_seq: ++inputSeq.current };
    if (data.type === "configure") {
      queued.current = data;
      if (!configTimer.current)
        configTimer.current = setTimeout(() => {
          configTimer.current = null;
          if (
            ws.current?.readyState === WebSocket.OPEN &&
            ["construction", "simulation"].includes(
              current.current?.phase ?? "",
            )
          )
            ws.current.send(JSON.stringify(queued.current));
        }, 80);
      return;
    }
    if (data.type === "ready" && configTimer.current) {
      clearTimeout(configTimer.current);
      configTimer.current = null;
    }
    if (ws.current?.readyState === WebSocket.OPEN)
      ws.current.send(JSON.stringify(data));
  };
  const connect = () => {
    if (!intent.current) return;
    setStatus("connecting · waking server");
    fetch(API + "/health").catch(() => {});
    const socket = new WebSocket(API.replace(/^http/, "ws") + "/ws");
    ws.current = socket;
    socket.onopen = () => {
      setStatus("connected");
      send(intent.current);
    };
    socket.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.type === "identity") {
        playerId.current = d.id;
        setMe(d.id);
        setCode(d.code);
        intent.current = {
          type: "join",
          code: d.code,
          name: intent.current.name,
          token: d.token,
        };
        sessionStorage.setItem("ft-session", JSON.stringify(intent.current));
        history.replaceState(null, "", "?room=" + d.code);
        sequence.current = -1;
      }
      if (d.type === "state" && d.state.seq > sequence.current) {
        const s: State = d.state,
          old = current.current;
        sequence.current = s.seq;
        const p = s.players.find((p) => p.id === playerId.current);
        if (
          !old ||
          old.code !== s.code ||
          old.round !== s.round ||
          old.match !== s.match ||
          old.phase !== s.phase
        ) {
          if (p) {
            setGenerators(p.generators);
            genRef.current = p.generators;
            setAngle(p.angle);
            angleRef.current = p.angle;
          }
        }
        current.current = s;
        setState(s);
        setOffset(s.server_time - Date.now() / 1000);
      }
      if (d.type === "error") {
        setError(d.message);
        if (
          /not found|room is full|already started|use a name/.test(d.message)
        ) {
          intent.current = null;
          sessionStorage.removeItem("ft-session");
          setState(null);
          current.current = null;
        }
      }
      if (d.type === "pong")
        setOffset(d.server_time - (d.client_time + Date.now() / 1000) / 2);
    };
    socket.onclose = (e) => {
      if (e.code === 4001) {
        intent.current = null;
        setStatus("opened in another tab");
        return;
      }
      setStatus(intent.current ? "reconnecting" : "not connected");
      if (intent.current) retry.current = setTimeout(connect, 1800);
    };
    socket.onerror = () => setStatus("connecting · waking server");
  };
  useEffect(() => {
    const saved = sessionStorage.getItem("ft-session");
    if (saved)
      try {
        const s = JSON.parse(saved);
        if (!code || code === s.code) {
          intent.current = s;
          setName(s.name);
          connect();
        }
      } catch {}
    const tick = setInterval(() => setNow(Date.now()), 100),
      ping = setInterval(
        () => send({ type: "ping", client_time: Date.now() / 1000 }),
        5000,
      );
    return () => {
      intent.current = null;
      clearInterval(tick);
      clearInterval(ping);
      if (retry.current) clearTimeout(retry.current);
      if (configTimer.current) clearTimeout(configTimer.current);
      ws.current?.close();
    };
  }, []);
  const join = (type: string) => {
    setError("");
    localStorage.setItem("ft-name", name);
    intent.current = { type, name, code: code.trim().toUpperCase() };
    connect();
  };
  const change = (gs: Generator[]) => {
    genRef.current = gs;
    setGenerators(gs);
    send({
      type: "configure",
      match: state?.match,
      round: state?.round,
      angle: angleRef.current,
      generators: gs,
    });
  };
  const aim = (a: number) => {
    angleRef.current = a;
    setAngle(a);
    send({
      type: "configure",
      match: state?.match,
      round: state?.round,
      angle: a,
      generators: genRef.current,
    });
  };
  const own = state?.players.find((p) => p.id === me),
    host = state?.host === me,
    live = state?.phase === "simulation",
    editable = live || state?.phase === "construction",
    active = editable || state?.phase === "results",
    seconds = state?.deadline
      ? Math.max(0, Math.ceil(state.deadline - now / 1000 - offset))
      : 0,
    best = Math.max(
      ...(state?.players.map((p) => Math.round(p.score * 10)) || [0]),
    ),
    winners =
      state?.players.filter((p) => Math.round(p.score * 10) === best) || [],
    liveTime = state?.live?.time ?? 0;
  return (
    <main className={active ? "playing" : ""}>
      <header>
        <a href="/" className="wordmark">
          FIELD THEORY<span>a game of invisible forces</span>
        </a>
        <div className="header-actions">
          <button onClick={() => setRules(true)}>how to play</button>
          <div className="connection">
            <i className={status === "connected" ? "online" : ""} />
            {status}
          </div>
        </div>
      </header>
      <section className="intro">
        <div className="eyebrow">CHARGES · CURVES · QUIET COMPETITION</div>
        <h1>
          {!state
            ? "A little charge.\nA change of course."
            : state.phase === "lobby"
              ? "Good company.\nUnpredictable physics."
              : state.phase === "finished"
                ? winners.length > 1
                  ? "A beautiful tie."
                  : winners[0]?.id === me
                    ? "You found your flow."
                    : `${winners[0]?.name} found the flow.`
                : live
                  ? "Keep the stream flowing."
                  : "Shape the field."}
        </h1>
        <p>
          Red repels. Blue attracts. Purple bends moving particles.
          <br />
          Three rounds. Live controls. A minute to find your flow.
        </p>
      </section>
      <div className="game-layout">
        <section className="arena-section">
          <div className="arena-top">
            <span>{state ? `ROOM ${state.code}` : "THE PLAYING FIELD"}</span>
            <span>
              {state
                ? state.phase === "lobby"
                  ? "waiting for players"
                  : `ROUND ${state.round} / ${state.rules?.rounds ?? 3}`
                : "02 — 04 PLAYERS"}
            </span>
          </div>
          <div className="arena-wrap">
            <Arena
              state={state}
              me={me}
              generators={generators}
              angle={angle}
              onChange={change}
              onAim={aim}
              kind={kind}
              mode={mode}
            />
            {state && (
              <div className="phase-pill">
                {
                  (
                    {
                      construction: "quick setup",
                      simulation: "live · aim & move your fields",
                      results: "round over",
                      finished: "match complete",
                      lobby: "waiting for players",
                    } as Record<string, string>
                  )[state.phase]
                }
                {state.deadline && <b>{seconds}s</b>}
              </div>
            )}
            {active && state && (
              <div className="arena-scores">
                {state.players.map((p, i) => (
                  <span key={p.id} style={{ color: colors[i] }}>
                    {p.id === me ? "you" : p.name.slice(0, 8)}{" "}
                    <b>{p.score.toFixed(1)}</b>
                  </span>
                ))}
              </div>
            )}
            {state?.notices.map((n, i) => (
              <div
                className="pickup-notice"
                style={{ bottom: 15 + i * 26 }}
                key={n.text + n.until}
              >
                {n.text}
              </div>
            ))}
          </div>
          <div className="arena-footer">
            <span>F = q(E + v × B)</span>
            <span>
              {editable
                ? mode === "aim"
                  ? "drag arena to aim · drag your fields to move"
                  : "tap to place · drag your fields to move"
                : "solid outline + “you” label = your fields"}
            </span>
          </div>
        </section>
        <aside>
          <div className="panel-number">
            {editable ? "02 / LIVE CONTROLS" : "01 / YOUR ROOM"}
          </div>
          {!state ? (
            <>
              <h2>
                Bring a friend.
                <br />
                Bend a trajectory.
              </h2>
              <label htmlFor="name">your name</label>
              <input
                id="name"
                maxLength={20}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. ada"
              />
              <button
                className="primary"
                disabled={!name.trim() || status.startsWith("connecting")}
                onClick={() => join("create")}
              >
                create a room ↗
              </button>
              <div className="or">or join your friends</div>
              <label htmlFor="code">room code</label>
              <div className="join-row">
                <input
                  id="code"
                  maxLength={5}
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="ABCDE"
                />
                <button
                  disabled={
                    !name.trim() ||
                    code.length !== 5 ||
                    status.startsWith("connecting")
                  }
                  onClick={() => join("join")}
                >
                  join →
                </button>
              </div>
              <p className="fine">2–4 players · no accounts · free to play</p>
            </>
          ) : (
            <>
              <div className="room-heading">
                <h2>{state.code}</h2>
                <button
                  onClick={() =>
                    navigator.clipboard
                      .writeText(location.href)
                      .then(() => {
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      })
                      .catch(() =>
                        setError("copy the URL from your address bar"),
                      )
                  }
                >
                  {copied ? "copied" : "copy invite ↗"}
                </button>
              </div>
              <div className="players">
                {state.players.map((p, i) => (
                  <div className="player" key={p.id}>
                    <i style={{ background: colors[i] }} />
                    <span>
                      <b className="player-number" style={{ color: colors[i] }}>
                        {i + 1}
                      </b>
                      {p.name}
                      {p.id === me ? " (you)" : ""}
                      <small>
                        {!p.connected
                          ? "disconnected"
                          : state.phase === "construction" && p.ready
                            ? "ready"
                            : state.phase === "simulation"
                              ? "live"
                              : p.id === state.host
                                ? "host"
                                : "connected"}
                      </small>
                    </span>
                    <strong>
                      {p.score.toFixed(1)}
                      <small>pressure s</small>
                    </strong>
                  </div>
                ))}
              </div>
              {state.phase === "lobby" && (
                <>
                  <p className="hint">
                    Share the code. Three rounds of live play. No waiting for a
                    trajectory to finish before making your next move.
                  </p>
                  {host ? (
                    <button
                      className="primary"
                      disabled={
                        state.players.filter((p) => p.connected).length < 2
                      }
                      onClick={() => send({ type: "start" })}
                    >
                      start match ↗
                    </button>
                  ) : (
                    <p>waiting for the host</p>
                  )}
                </>
              )}
              {editable && (
                <div className="controls">
                  <div className="mode-switch">
                    <button
                      className={mode === "aim" ? "selected" : ""}
                      onClick={() => setMode("aim")}
                    >
                      ↗ aim cannon
                    </button>
                    <button
                      className={mode === "place" ? "selected" : ""}
                      onClick={() => setMode("place")}
                    >
                      ＋ place fields
                    </button>
                  </div>
                  <div className="tools">
                    {(["positive", "negative", "coil"] as const).map((k, i) => (
                      <button
                        className={
                          kind === k && mode === "place" ? "selected" : ""
                        }
                        key={k}
                        onClick={() => {
                          setKind(k);
                          setMode("place");
                        }}
                      >
                        <b
                          style={{
                            color: ["#c77460", "#658da8", "#9482b2"][i],
                          }}
                        >
                          {["+", "−", "⊙"][i]}
                        </b>
                        {["repel", "attract", "curve"][i]}
                      </button>
                    ))}
                  </div>
                  <div className="placed">
                    <span className="fine">
                      your fields {generators.length}/2
                    </span>
                    {generators.map((g, i) => (
                      <button
                        key={i}
                        onClick={() =>
                          change(generators.filter((_, j) => j !== i))
                        }
                      >
                        {i + 1} ·{" "}
                        {g.kind === "coil"
                          ? "coil"
                          : g.kind === "positive"
                            ? "+"
                            : "−"}{" "}
                        ×
                      </button>
                    ))}
                  </div>
                  <label htmlFor="aim">
                    firing angle{" "}
                    <span>
                      {Math.round(((angle * 180) / Math.PI + 360) % 360)}°
                    </span>
                  </label>
                  <input
                    id="aim"
                    type="range"
                    min="0"
                    max="360"
                    value={((angle * 180) / Math.PI + 360) % 360}
                    onChange={(e) => aim((+e.target.value * Math.PI) / 180)}
                  />
                  {state.phase === "construction" ? (
                    <button
                      className="primary"
                      onClick={() =>
                        send({
                          type: own?.ready ? "configure" : "ready",
                          round: state.round,
                          match: state.match,
                          angle: angleRef.current,
                          generators: genRef.current,
                        })
                      }
                    >
                      {own?.ready ? "ready ✓ · edit" : "ready · start early ↗"}
                    </button>
                  ) : (
                    <p className="live-hint">
                      ● firing continuously · controls stay live
                    </p>
                  )}
                  <div className="effects">
                    {Object.entries(own?.effects ?? {})
                      .filter(([, until]) => until > liveTime)
                      .map(([kind, until]) => (
                        <span
                          className={
                            ["slow", "weaken", "drift"].includes(kind)
                              ? "harmful"
                              : ""
                          }
                          key={kind}
                        >
                          {effectNames[kind]} · {Math.ceil(until - liveTime)}s
                        </span>
                      ))}
                  </div>
                  <p className="fine">
                    hit labeled pickups · effects last 6s · one coil max
                  </p>
                </div>
              )}
              {state.phase === "results" && (
                <p className="hint">
                  Pressure earned.{" "}
                  {state.round < 3
                    ? "Next round starts shortly."
                    : "Final scores coming up."}
                </p>
              )}
              {state.phase === "finished" && (
                <>
                  <p>
                    {winners.length > 1
                      ? "shared victory"
                      : `${winners[0]?.name} wins`}{" "}
                    · {(best / 10).toFixed(1)} pressure seconds
                  </p>
                  {host && (
                    <button
                      className="primary"
                      onClick={() => send({ type: "rematch" })}
                    >
                      play again ↗
                    </button>
                  )}
                </>
              )}
              <button
                className="leave"
                onClick={() => {
                  intent.current = null;
                  sessionStorage.removeItem("ft-session");
                  ws.current?.close();
                  setState(null);
                  current.current = null;
                  history.replaceState(null, "", "/");
                  setStatus("not connected");
                }}
              >
                leave room
              </button>
            </>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
              <button onClick={() => setError("")}>×</button>
            </p>
          )}
        </aside>
      </div>
      <section className="guide">
        <div>
          <span>01</span>
          <h3>Arrange the invisible.</h3>
          <p>
            Eight seconds to start. Place two fields; your numbered badges and
            “you” labels show what you control.
          </p>
        </div>
        <div>
          <span>02</span>
          <h3>Stay in the flow.</h3>
          <p>
            Your cannon never stops. Aim and move fields for sixty seconds.
            Rival streams push one another aside.
          </p>
        </div>
        <div>
          <span>03</span>
          <h3>Chase the advantage.</h3>
          <p>
            Hit labeled pickups to boost yourself or disrupt rivals. Sustained
            reactor contact earns pressure seconds.
          </p>
        </div>
      </section>
      <footer>
        <span>FIELD THEORY</span>
        <button onClick={() => setRules(true)}>rules & boosters ↗</button>
        <span>built on classical physics</span>
      </footer>
      {rules && <Rules close={() => setRules(false)} />}
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
