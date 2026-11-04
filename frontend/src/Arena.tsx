import { useEffect, useRef } from "react";
import {
  centers,
  colors,
  type State,
  type Generator,
  type Particle,
} from "./types";
const fieldColor = (g: Generator) =>
  g.kind === "positive"
    ? "#ca7865"
    : g.kind === "negative"
      ? "#5d8fae"
      : "#967bb4";
type Props = {
  state: State | null;
  me: string;
  generators: Generator[];
  angle: number;
  onChange: (g: Generator[]) => void;
  onAim: (a: number) => void;
  kind: Generator["kind"];
  mode: "place" | "aim";
};
export function Arena(props: Props) {
  const canvas = useRef<HTMLCanvasElement>(null),
    current = useRef(props),
    drag = useRef<number | null>(null),
    aiming = useRef(false);
  current.current = props;
  const motion = useRef({
    received: 0,
    seq: -1,
    previous: new Map<number, Particle>(),
    latest: new Map<number, Particle>(),
    trails: new Map<number, [number, number][]>(),
    round: "",
  });
  useEffect(() => {
    let raf = 0;
    const ctx = canvas.current!.getContext("2d")!;
    const draw = () => {
      const c = canvas.current!,
        rect = c.getBoundingClientRect(),
        dpr = Math.min(devicePixelRatio, 2),
        w = rect.width,
        h = rect.height;
      if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
        c.width = Math.round(w * dpr);
        c.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const { state: s, me, generators, angle } = current.current,
        ps = s?.players ?? [],
        cs = centers(Math.max(2, ps.length)),
        editable = s?.phase === "construction" || s?.phase === "simulation";
      const gs = s
        ? ps.flatMap((p, owner) =>
            (p.id === me && editable ? generators : p.generators).map(
              (g, index) => ({ ...g, owner, index, mine: p.id === me }),
            ),
          )
        : [
            {
              kind: "positive" as const,
              x: 0.35,
              y: 0.42,
              owner: 0,
              index: 0,
              mine: true,
            },
            {
              kind: "negative" as const,
              x: 0.64,
              y: 0.6,
              owner: 1,
              index: 0,
              mine: false,
            },
            {
              kind: "coil" as const,
              x: 0.53,
              y: 0.35,
              owner: 0,
              index: 1,
              mine: true,
            },
          ];
      ctx.strokeStyle = "#33333309";
      ctx.lineWidth = 0.7;
      for (let x = 0.05; x < 1; x += 0.05) {
        ctx.beginPath();
        ctx.moveTo(x * w, 0);
        ctx.lineTo(x * w, h);
        ctx.stroke();
      }
      for (let y = 0.05; y < 1; y += 0.05) {
        ctx.beginPath();
        ctx.moveTo(0, y * h);
        ctx.lineTo(w, y * h);
        ctx.stroke();
      }
      // Electric streamlines use the same softened Coulomb directions as the server.
      for (let sx = 0.045; sx < 1; sx += 0.09)
        for (let sy = 0.045; sy < 1; sy += 0.12) {
          let x = sx,
            y = sy;
          ctx.beginPath();
          ctx.moveTo(x * w, y * h);
          for (let k = 0; k < 30; k++) {
            let ex = 0,
              ey = 0;
            for (const g of gs) {
              if (g.kind === "coil") continue;
              const dx = x - g.x,
                dy = y - g.y,
                weak =
                  (ps[g.owner]?.effects.weaken ?? 0) > (s?.live?.time ?? 0)
                    ? 0.45
                    : 1,
                q = (g.kind === "positive" ? 1 : -1) * weak,
                den = (dx * dx + dy * dy + 0.065 ** 2) ** 1.5;
              ex += (q * dx) / den;
              ey += (q * dy) / den;
            }
            for (const o of s?.arena?.objects ?? []) {
              if (o.kind !== "lens") continue;
              const dx = x - o.x,
                dy = y - o.y;
              const factor =
                (((-0.9 / 0.018) * o.strength) / o.radius) *
                Math.exp(-(dx * dx + dy * dy) / (2 * o.radius ** 2));
              ex += factor * dx;
              ey += factor * dy;
            }
            const n = Math.hypot(ex, ey);
            if (n < 0.01) break;
            x += (ex / n) * 0.006;
            y += (ey / n) * 0.006;
            ctx.lineTo(x * w, y * h);
          }
          ctx.strokeStyle = "#73858f52";
          ctx.lineWidth = 1.55;
          ctx.stroke();
        }
      for (const o of s?.arena?.objects ?? []) {
        const x = o.x * w,
          y = o.y * h;
        ctx.fillStyle = o.kind === "lens" ? "#618a9b12" : "#967bb412";
        ctx.strokeStyle = o.kind === "lens" ? "#618a9b99" : "#967bb499";
        ctx.lineWidth = 1.3;
        ctx.setLineDash([3, 4]);
        ctx.beginPath();
        ctx.ellipse(x, y, o.radius * w, o.radius * h, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.font = "22px sans-serif";
        ctx.textAlign = "center";
        ctx.fillStyle = o.kind === "lens" ? "#567e90" : "#87669f";
        ctx.fillText(
          o.kind === "lens" ? "◎" : o.strength > 0 ? "↺" : "↻",
          x,
          y + 7,
        );
        ctx.font = "10px sans-serif";
        ctx.fillText(o.label, x, y + o.radius * h + 14);
        ctx.fillStyle = "#777d70";
        ctx.fillText("arena · fixed", x, y + o.radius * h + 27);
      }
      cs.forEach(([x, y], i) => {
        const p = ps[i],
          shield = (p?.effects.shield ?? 0) > (s?.live?.time ?? 0),
          contact = s?.live?.contact.some(
            (row, owner) => owner !== i && row[i],
          );
        ctx.setLineDash([2, 5]);
        ctx.strokeStyle = colors[i] + "55";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.ellipse(x * w, y * h, 0.105 * w, 0.105 * h, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        if (shield || contact) {
          ctx.strokeStyle = shield ? "#718f72" : colors[i];
          ctx.lineWidth = shield ? 3 : 1.5;
          ctx.beginPath();
          ctx.ellipse(x * w, y * h, 0.042 * w, 0.042 * h, 0, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.fillStyle = colors[i];
        ctx.beginPath();
        ctx.ellipse(x * w, y * h, 0.029 * w, 0.029 * h, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = "12px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(String(i + 1), x * w, y * h + 4);
        ctx.fillStyle = "#525c4c";
        ctx.font = "10px sans-serif";
        ctx.fillText(
          p
            ? `${p.name}${p.id === me ? " · you" : ""}`
            : i === 0
              ? "you"
              : "opponent",
          x * w,
          y * h + 0.063 * h,
        );
        if (editable && p) {
          let a = p.id === me ? angle : p.angle;
          if ((p.effects.drift ?? 0) > (s?.live?.time ?? 0))
            a += 0.14 * Math.sin((s?.live?.time ?? 0) * 5 + i);
          ctx.strokeStyle = colors[i];
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(
            (x + Math.cos(a) * 0.027) * w,
            (y + Math.sin(a) * 0.027) * h,
          );
          ctx.lineTo(
            (x + Math.cos(a) * 0.085) * w,
            (y + Math.sin(a) * 0.085) * h,
          );
          ctx.stroke();
        }
      });
      gs.forEach((g) => {
        ctx.strokeStyle = fieldColor(g);
        ctx.fillStyle = fieldColor(g);
        ctx.lineWidth = 1.5;
        if (g.kind === "coil") {
          for (let i = 0; i < 3; i++) {
            const rad =
              0.018 + i * 0.01 + Math.sin(performance.now() / 1000 + i) * 0.001;
            ctx.globalAlpha = 1 - i * 0.25;
            ctx.beginPath();
            ctx.ellipse(g.x * w, g.y * h, rad * w, rad * h, 0, 0, Math.PI * 2);
            ctx.stroke();
          }
          ctx.globalAlpha = 1;
        } else {
          ctx.beginPath();
          ctx.arc(g.x * w, g.y * h, 10, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.strokeStyle = g.mine ? "#394931" : colors[g.owner];
        ctx.lineWidth = g.mine ? 2.5 : 1.5;
        ctx.setLineDash(g.mine ? [] : [3, 3]);
        ctx.beginPath();
        ctx.arc(g.x * w, g.y * h, g.kind === "coil" ? 17 : 14, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = g.kind === "coil" ? fieldColor(g) : "#fff";
        ctx.font = "bold 14px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(
          g.kind === "positive" ? "+" : g.kind === "negative" ? "−" : "⊙",
          g.x * w,
          g.y * h + 5,
        );
        const label = `${g.mine ? "you" : (ps[g.owner]?.name ?? "opponent").slice(0, 8)} · ${g.index + 1}`;
        ctx.font = g.mine ? "bold 10px sans-serif" : "10px sans-serif";
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = "#f8f8f0ee";
        ctx.fillRect(g.x * w - tw / 2 - 5, g.y * h + 19, tw + 10, 15);
        ctx.fillStyle = g.mine ? "#34462e" : colors[g.owner];
        ctx.fillText(label, g.x * w, g.y * h + 30);
        ctx.fillStyle = colors[g.owner];
        ctx.beginPath();
        ctx.arc(g.x * w + 12, g.y * h - 12, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = "8px sans-serif";
        ctx.fillText(String(g.owner + 1), g.x * w + 12, g.y * h - 9);
      });
      for (const b of s?.boosters ?? []) {
        const x = b.x * w,
          y = b.y * h,
          own = b.target === "self";
        ctx.fillStyle = own ? "#e5eddeee" : "#f0e1dbee";
        ctx.strokeStyle = own ? "#7b9564" : "#b17b66";
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.arc(x, y, 12, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = own ? "#597545" : "#965d48";
        ctx.font = "bold 14px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(own ? "+" : "↯", x, y + 5);
        ctx.font = "bold 10px sans-serif";
        const label = b.label,
          tw = ctx.measureText(label).width;
        ctx.fillStyle = "#faf9f0ee";
        ctx.fillRect(x - tw / 2 - 4, y + 16, tw + 8, 15);
        ctx.fillStyle = own ? "#597545" : "#965d48";
        ctx.fillText(label, x, y + 27);
      }
      const m = motion.current,
        key = s ? `${s.code}-${s.match}-${s.round}` : "";
      if (key !== m.round) {
        m.round = key;
        m.seq = -1;
        m.previous.clear();
        m.latest.clear();
        m.trails.clear();
      }
      if (s?.live && s.seq !== m.seq) {
        m.previous = m.latest;
        m.latest = new Map(s.live.particles.map((p) => [p[0], p]));
        m.received = performance.now();
        m.seq = s.seq;
        for (const p of s.live.particles) {
          const trail = m.trails.get(p[0]) ?? [],
            last = trail.at(-1);
          if (last && Math.hypot(last[0] - p[2], last[1] - p[3]) > 0.2)
            trail.length = 0;
          trail.push([p[2], p[3]]);
          if (trail.length > 9) trail.shift();
          m.trails.set(p[0], trail);
        }
        for (const id of m.trails.keys())
          if (!m.latest.has(id)) m.trails.delete(id);
      }
      const alpha = Math.min(1, (performance.now() - m.received) / 100);
      if (s?.phase === "simulation" || s?.phase === "results")
        for (const [id, p] of m.latest) {
          const old = m.previous.get(id),
            same = old && Math.hypot(old[2] - p[2], old[3] - p[3]) < 0.2;
          const x = same ? old[2] + (p[2] - old[2]) * alpha : p[2],
            y = same ? old[3] + (p[3] - old[3]) * alpha : p[3];
          const trail = m.trails.get(id) ?? [];
          ctx.strokeStyle = colors[p[1]] + "85";
          ctx.lineWidth = 1.7;
          ctx.beginPath();
          trail.forEach(([tx, ty], i) =>
            i ? ctx.lineTo(tx * w, ty * h) : ctx.moveTo(tx * w, ty * h),
          );
          ctx.stroke();
          ctx.fillStyle = colors[p[1]];
          ctx.beginPath();
          ctx.arc(x * w, y * h, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, []);
  const point = (e: React.PointerEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    return {
      x: (e.clientX - r.left) / r.width,
      y: (e.clientY - r.top) / r.height,
    };
  };
  const legal = (g: Generator) =>
    g.x >= 0.025 &&
    g.x <= 0.975 &&
    g.y >= 0.025 &&
    g.y <= 0.975 &&
    (props.state?.arena?.objects ?? []).every(
      (o) => Math.hypot(o.x - g.x, o.y - g.y) >= o.radius + 0.025,
    ) &&
    centers(props.state?.players.length || 2).every(
      ([x, y]) => Math.hypot(x - g.x, y - g.y) >= 0.105,
    );
  const aim = (p: { x: number; y: number }) => {
    const i = props.state?.players.findIndex((p) => p.id === props.me) ?? 0;
    const [x, y] = centers(props.state?.players.length || 2)[Math.max(0, i)];
    props.onAim((Math.atan2(p.y - y, p.x - x) + Math.PI * 2) % (Math.PI * 2));
  };
  return (
    <canvas
      ref={canvas}
      aria-label="shared electromagnetic arena"
      onPointerDown={(e) => {
        if (!["construction", "simulation"].includes(props.state?.phase ?? ""))
          return;
        const p = point(e),
          i = props.generators.findIndex(
            (g) => Math.hypot(g.x - p.x, g.y - p.y) < 0.045,
          );
        drag.current = i >= 0 ? i : null;
        aiming.current = i < 0 && props.mode === "aim";
        e.currentTarget.setPointerCapture(e.pointerId);
        if (aiming.current) {
          aim(p);
          return;
        }
        if (
          i < 0 &&
          props.generators.length < 2 &&
          !(
            props.kind === "coil" &&
            props.generators.some((g) => g.kind === "coil")
          )
        ) {
          const g = { ...p, kind: props.kind };
          if (legal(g)) {
            props.onChange([...props.generators, g]);
            drag.current = props.generators.length;
          }
        }
      }}
      onPointerMove={(e) => {
        if (!e.buttons) return;
        if (aiming.current) {
          aim(point(e));
          return;
        }
        if (drag.current === null) return;
        const g = { ...props.generators[drag.current], ...point(e) };
        if (legal(g))
          props.onChange(
            props.generators.map((v, i) => (i === drag.current ? g : v)),
          );
      }}
      onPointerUp={() => {
        drag.current = null;
        aiming.current = false;
      }}
      onPointerCancel={() => {
        drag.current = null;
        aiming.current = false;
      }}
    />
  );
}
