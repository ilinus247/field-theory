import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Arena } from "./Arena";
import { colors, type State, type Generator } from "./types";
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
    [offset, setOffset] = useState(0),
    [now, setNow] = useState(Date.now()),
    [copied, setCopied] = useState(false);
  const ws = useRef<WebSocket | null>(null),
    reconnect = useRef<ReturnType<typeof setTimeout> | null>(null),
    intent = useRef<any>(null),
    sequence = useRef(-1),
    round = useRef(0),
    phase = useRef(""),
    angleRef = useRef(angle),
    genRef = useRef(generators);
  angleRef.current = angle;
  genRef.current = generators;
  const queuedConfig = useRef<any>(null);
  const configTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const send = (v: any) => {
    // Coalesce pointer/slider updates to 10 Hz while preserving the final position.
    // Ready carries the complete configuration and cancels pending edits.
    if (v.type === "configure") {
      queuedConfig.current = v;
      if (!configTimer.current)
        configTimer.current = setTimeout(() => {
          configTimer.current = null;
          if (
            ws.current?.readyState === WebSocket.OPEN &&
            phase.current === "construction"
          )
            ws.current.send(JSON.stringify(queuedConfig.current));
        }, 100);
      return;
    }
    if (v.type === "ready" && configTimer.current) {
      clearTimeout(configTimer.current);
      configTimer.current = null;
    }
    if (ws.current?.readyState === WebSocket.OPEN)
      ws.current.send(JSON.stringify(v));
  };
  const connect = () => {
    if (!intent.current) return;
    setStatus("connecting · waking server");
    fetch(API + "/health").catch(() => {});
    const sock = new WebSocket(API.replace(/^http/, "ws") + "/ws");
    ws.current = sock;
    sock.onopen = () => {
      setStatus("connected");
      send(intent.current);
    };
    sock.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.type === "identity") {
        setMe(d.id);
        setCode(d.code);
        intent.current = { type: "join", code: d.code, name, token: d.token };
        sessionStorage.setItem("ft-session", JSON.stringify(intent.current));
        history.replaceState(null, "", "?room=" + d.code);
        sequence.current = -1;
      }
      if (d.type === "state" && d.state.seq > sequence.current) {
        const s: State = d.state;
        sequence.current = s.seq;
        setState(s);
        setOffset(s.server_time - Date.now() / 1000);
        if (round.current !== s.round || phase.current !== s.phase) {
          const id = sessionStorage.getItem("ft-id");
          const own = s.players.find((p) => p.id === id);
          if (own) {
            setGenerators(own.generators);
            setAngle(own.angle);
          }
          round.current = s.round;
          phase.current = s.phase;
        }
      }
      if (d.type === "identity") sessionStorage.setItem("ft-id", d.id);
      if (d.type === "error") {
        setError(d.message);
        if (/not found|full|started|name/.test(d.message)) {
          intent.current = null;
          sessionStorage.removeItem("ft-session");
          setState(null);
        }
      }
      if (d.type === "pong") {
        const t = Date.now() / 1000;
        setOffset(d.server_time - (d.client_time + t) / 2);
      }
    };
    sock.onclose = (e) => {
      setStatus("reconnecting");
      if (e.code === 4001) {
        intent.current = null;
        setStatus("opened in another tab");
        return;
      }
      if (intent.current) reconnect.current = setTimeout(connect, 1800);
      else setStatus("not connected");
    };
    sock.onerror = () => setStatus("connecting · waking server");
  };
  useEffect(() => {
    const saved = sessionStorage.getItem("ft-session");
    if (saved) {
      try {
        const s = JSON.parse(saved);
        if (!code || code === s.code) {
          intent.current = s;
          setName(s.name);
          connect();
        }
      } catch {}
    }
    const tick = setInterval(() => setNow(Date.now()), 100);
    const ping = setInterval(
      () => send({ type: "ping", client_time: Date.now() / 1000 }),
      5000,
    );
    return () => {
      clearInterval(tick);
      clearInterval(ping);
      intent.current = null;
      if (reconnect.current) clearTimeout(reconnect.current);
      if (configTimer.current) clearTimeout(configTimer.current);
      ws.current?.close();
    };
  }, []);
  const own = state?.players.find((p) => p.id === me),
    host = state?.host === me,
    construction = state?.phase === "construction";
  const change = (gs: Generator[]) => {
    setGenerators(gs);
    send({
      type: "configure",
      round: state?.round,
      match: state?.match,
      angle: angleRef.current,
      generators: gs,
    });
  };
  const join = (type: string) => {
    setError("");
    localStorage.setItem("ft-name", name);
    intent.current = { type, name, code: code.trim().toUpperCase() };
    connect();
  };
  const seconds = state?.deadline
    ? Math.max(0, Math.ceil(state.deadline - now / 1000 - offset))
    : 0;
  const best = Math.max(...(state?.players.map((p) => p.score) || [0]));
  const winners = state?.players.filter((p) => p.score === best) || [];
  return (
    <main>
      <header>
        <a href="/" className="wordmark">
          FIELD THEORY<span>a game of invisible forces</span>
        </a>
        <div className="connection">
          <i className={status === "connected" ? "online" : ""} />
          {status}
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
                : "Place your fields.\nLet physics take over."}
        </h1>
        <p>
          Red repels. Blue attracts. Purple bends moving particles.
          <br />A shared arena. Five rounds. One elegant experiment.
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
                  : `ROUND ${state.round} / 5`
                : "02 — 04 PLAYERS"}
            </span>
          </div>
          <div className="arena-wrap">
            <Arena
              state={state}
              me={me}
              offset={offset}
              generators={generators}
              onChange={change}
              kind={kind}
            />
            {state && (
              <div className="phase-pill">
                {
                  (
                    {
                      construction: "place your fields",
                      simulation: "simulating…",
                      computing: "calculating curves…",
                      results: "round over",
                      finished: "match complete",
                      lobby: "waiting for players",
                    } as Record<string, string>
                  )[state.phase]
                }
                {state.deadline && <b>{seconds}s</b>}
              </div>
            )}
          </div>
          <div className="arena-footer">
            <span>F = q(E + v × B)</span>
            <span>
              {construction
                ? "tap to place · drag to move"
                : "the smallest forces change everything"}
            </span>
          </div>
        </section>
        <aside>
          {!state ? (
            <>
              <div className="panel-number">01 / ENTER THE FIELD</div>
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
                create a room <span>↗</span>
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
                  disabled={!name.trim() || code.length !== 5}
                  onClick={() => join("join")}
                >
                  join →
                </button>
              </div>
              <p className="fine">2–4 players · no accounts · free to play</p>
            </>
          ) : (
            <>
              <div className="panel-number">
                {state.phase === "construction"
                  ? "02 / SHAPE THE FIELD"
                  : "01 / YOUR ROOM"}
              </div>
              <div className="room-heading">
                <h2>{state.code}</h2>
                <button
                  onClick={() => {
                    navigator.clipboard
                      .writeText(location.href)
                      .then(() => {
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      })
                      .catch(() =>
                        setError("copy the room URL from your address bar"),
                      );
                  }}
                >
                  {copied ? "copied" : "copy invite ↗"}
                </button>
              </div>
              <div className="players">
                {state.players.map((p, i) => (
                  <div className="player" key={p.id}>
                    <i style={{ background: colors[i] }} />
                    <span>
                      {p.name}
                      {p.id === me ? " (you)" : ""}
                      <small>
                        {!p.connected
                          ? "disconnected"
                          : p.ready
                            ? "ready"
                            : p.id === state.host
                              ? "host"
                              : "connected"}
                      </small>
                    </span>
                    <strong>{p.score}</strong>
                  </div>
                ))}
              </div>
              {state.phase === "lobby" && (
                <>
                  <p className="hint">
                    Share the room code. The host starts when everyone has
                    arrived.
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
              {construction && (
                <>
                  <label>
                    choose a field <span>{generators.length}/2 placed</span>
                  </label>
                  <div className="tools">
                    {(["positive", "negative", "coil"] as const).map((k, i) => (
                      <button
                        className={kind === k ? "selected" : ""}
                        key={k}
                        onClick={() => setKind(k)}
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
                    {generators.map((g, i) => (
                      <button
                        key={i}
                        onClick={() =>
                          change(generators.filter((_, j) => i !== j))
                        }
                      >
                        {g.kind === "coil"
                          ? "coil"
                          : g.kind === "positive"
                            ? "+ charge"
                            : "− charge"}{" "}
                        ×
                      </button>
                    ))}
                  </div>
                  <label htmlFor="aim">
                    firing angle{" "}
                    <span>{Math.round((angle * 180) / Math.PI)}°</span>
                  </label>
                  <input
                    id="aim"
                    type="range"
                    min="0"
                    max="360"
                    value={((angle * 180) / Math.PI + 360) % 360}
                    onChange={(e) => {
                      const a = (+e.target.value * Math.PI) / 180;
                      setAngle(a);
                      send({
                        type: "configure",
                        round: state.round,
                        match: state.match,
                        angle: a,
                        generators: genRef.current,
                      });
                    }}
                  />
                  <button
                    className="primary"
                    onClick={() =>
                      send({
                        type: own?.ready ? "configure" : "ready",
                        round: state.round,
                        match: state.match,
                        angle,
                        generators,
                      })
                    }
                  >
                    {own?.ready ? "ready ✓ · edit" : "ready to launch ↗"}
                  </button>
                  <p className="fine">
                    up to two fields · one coil · fixed launch power
                  </p>
                </>
              )}
              {state.phase === "results" && (
                <p className="hint">
                  {state.playback?.events.filter((e) => e.scored).length || 0}{" "}
                  hits this round.{" "}
                  {state.round < 5
                    ? "Next round begins shortly."
                    : "Final scores coming up."}
                </p>
              )}
              {state.phase === "finished" && (
                <>
                  <p>
                    {winners.length > 1
                      ? "shared victory"
                      : `${winners[0]?.name} wins`}{" "}
                    · {best} points
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
            Place two fields outside the protected reactor circles. Everyone
            shares the same forces.
          </p>
        </div>
        <div>
          <span>02</span>
          <h3>Find your angle.</h3>
          <p>
            Aim your particle, then get ready. You have twenty seconds to set
            things in motion.
          </p>
        </div>
        <div>
          <span>03</span>
          <h3>Let the curves decide.</h3>
          <p>
            All particles launch together. Hit an opponent’s reactor to score.
            Most points after five rounds wins.
          </p>
        </div>
      </section>
      <footer>
        <span>FIELD THEORY</span>
        <span>less control. more possibility.</span>
        <span>built on classical physics</span>
      </footer>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
