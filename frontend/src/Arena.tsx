import { useEffect, useRef } from "react";
import { centers, colors, type State, type Generator } from "./types";
const fieldColor = (g: Generator) =>
  g.kind === "positive"
    ? "#cf806f"
    : g.kind === "negative"
      ? "#709bb7"
      : "#9b87b8";
export function Arena({
  state,
  me,
  offset,
  generators,
  onChange,
  kind,
}: {
  state: State | null;
  me: string;
  offset: number;
  generators: Generator[];
  onChange: (g: Generator[]) => void;
  kind: Generator["kind"];
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    drag = useRef<number | null>(null),
    moved = useRef(false);
  const props = useRef({ state, me, offset, generators });
  props.current = { state, me, offset, generators };
  useEffect(() => {
    let raf = 0;
    const ctx = canvas.current!.getContext("2d")!;
    const draw = () => {
      const c = canvas.current!,
        r = c.getBoundingClientRect(),
        dpr = Math.min(devicePixelRatio, 2);
      if (c.width !== r.width * dpr || c.height !== r.height * dpr) {
        c.width = r.width * dpr;
        c.height = r.height * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = r.width,
        h = r.height;
      ctx.clearRect(0, 0, w, h);
      const { state: s, me, offset, generators } = props.current;
      const ps = s?.players ?? [];
      const cs = centers(ps.length || 2);
      const gs = s
        ? ps.flatMap((p) =>
            p.id === me && s.phase === "construction"
              ? generators
              : p.generators,
          )
        : [
            { kind: "positive" as const, x: 0.35, y: 0.42 },
            { kind: "negative" as const, x: 0.64, y: 0.6 },
            { kind: "coil" as const, x: 0.53, y: 0.35 },
          ];
      ctx.strokeStyle = "#33333308";
      ctx.lineWidth = 1;
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
      // Streamlines use the electric field equation; magnetic fields are shown separately.
      for (let sx = 0.045; sx < 1; sx += 0.09)
        for (let sy = 0.045; sy < 1; sy += 0.12) {
          let x = sx,
            y = sy;
          ctx.beginPath();
          ctx.moveTo(x * w, y * h);
          for (let k = 0; k < 24; k++) {
            let ex = 0,
              ey = 0;
            for (const g of gs) {
              if (g.kind === "coil") continue;
              let dx = x - g.x,
                dy = y - g.y,
                q = g.kind === "positive" ? 1 : -1,
                den = (dx * dx + dy * dy + 0.065 ** 2) ** 1.5;
              ex += (q * dx) / den;
              ey += (q * dy) / den;
            }
            let n = Math.hypot(ex, ey);
            if (n < 0.01) break;
            x += (ex / n) * 0.006;
            y += (ey / n) * 0.006;
            ctx.lineTo(x * w, y * h);
          }
          ctx.strokeStyle = "#7f8c941c";
          ctx.lineWidth = 0.7;
          ctx.stroke();
        }
      cs.forEach(([x, y], i) => {
        ctx.setLineDash([2, 5]);
        ctx.strokeStyle = colors[i] + "45";
        ctx.beginPath();
        ctx.ellipse(x * w, y * h, 0.105 * w, 0.105 * h, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = colors[i];
        ctx.beginPath();
        ctx.ellipse(x * w, y * h, 0.029 * w, 0.029 * h, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#f8f7f2";
        ctx.font = "12px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(String(i + 1), x * w, y * h + 4);
        ctx.fillStyle = "#72746f";
        ctx.font = "10px sans-serif";
        ctx.fillText(
          ps[i]?.name ?? (i === 0 ? "you" : "opponent"),
          x * w,
          y * h + 0.06 * h,
        );
        if (s?.phase === "construction") {
          const a = ps[i].angle;
          ctx.strokeStyle = colors[i] + "90";
          ctx.beginPath();
          ctx.moveTo(
            (x + Math.cos(a) * 0.045) * w,
            (y + Math.sin(a) * 0.045) * h,
          );
          ctx.lineTo(
            (x + Math.cos(a) * 0.095) * w,
            (y + Math.sin(a) * 0.095) * h,
          );
          ctx.stroke();
        }
      });
      gs.forEach((g) => {
        ctx.strokeStyle = fieldColor(g);
        ctx.fillStyle = fieldColor(g);
        if (g.kind === "coil") {
          for (let j = 0; j < 3; j++) {
            let rad =
              0.018 +
              j * 0.012 +
              Math.sin(performance.now() / 1000 + j) * 0.002;
            ctx.globalAlpha = 1 - j * 0.3;
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
        ctx.fillStyle = g.kind === "coil" ? fieldColor(g) : "#fff";
        ctx.font = "14px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(
          g.kind === "positive" ? "+" : g.kind === "negative" ? "−" : "·",
          g.x * w,
          g.y * h + 5,
        );
      });
      if (s?.playback) {
        const pb = s.playback,
          t = Math.max(0, Date.now() / 1000 + offset - pb.start),
          f = Math.min(pb.frames.length - 1, t / pb.frame_dt),
          index = Math.floor(f),
          alpha = f - index;
        ps.forEach((p, i) => {
          ctx.strokeStyle = colors[i];
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          let started = false;
          for (let j = Math.max(0, index - 35); j <= index; j++) {
            const pos = pb.frames[j]?.[i];
            if (!pos) break;
            if (!started) {
              ctx.moveTo(pos[0] * w, pos[1] * h);
              started = true;
            } else ctx.lineTo(pos[0] * w, pos[1] * h);
          }
          ctx.globalAlpha = 0.55;
          ctx.stroke();
          ctx.globalAlpha = 1;
          const a = pb.frames[index]?.[i],
            b = pb.frames[Math.min(index + 1, pb.frames.length - 1)]?.[i];
          if (a && t < 8) {
            const x = b ? a[0] + (b[0] - a[0]) * alpha : a[0],
              y = b ? a[1] + (b[1] - a[1]) * alpha : a[1];
            ctx.fillStyle = colors[i];
            ctx.beginPath();
            ctx.arc(x * w, y * h, 3.5, 0, Math.PI * 2);
            ctx.fill();
          }
        });
        for (const e of pb.events) {
          const age = t - e.time;
          if (age >= 0 && age < 1) {
            ctx.strokeStyle = e.scored ? "#c77460" : "#8a8b84";
            ctx.globalAlpha = 1 - age;
            ctx.beginPath();
            ctx.arc(e.x * w, e.y * h, 8 + age * 30, 0, Math.PI * 2);
            ctx.stroke();
            ctx.globalAlpha = 1;
          }
        }
      }
      if (!s) {
        ctx.strokeStyle = "#c7746066";
        ctx.lineWidth = 1.3;
        ctx.beginPath();
        for (let i = 0; i < 150; i++) {
          const t = i / 149,
            x = 0.15 + t * 0.7,
            y = 0.5 + Math.sin(t * Math.PI * 2) * 0.22 * Math.sin(t * Math.PI);
          if (i === 0) ctx.moveTo(x * w, y * h);
          else ctx.lineTo(x * w, y * h);
        }
        ctx.stroke();
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
    centers(state?.players.length || 2).every(
      ([x, y]) => Math.hypot(x - g.x, y - g.y) >= 0.105,
    );
  return (
    <canvas
      ref={canvas}
      aria-label="shared electromagnetic arena"
      onPointerDown={(e) => {
        if (state?.phase !== "construction") return;
        const p = point(e);
        const idx = generators.findIndex(
          (g) => Math.hypot(g.x - p.x, g.y - p.y) < 0.045,
        );
        drag.current = idx >= 0 ? idx : null;
        moved.current = false;
        e.currentTarget.setPointerCapture(e.pointerId);
        if (
          idx < 0 &&
          generators.length < 2 &&
          !(kind === "coil" && generators.some((g) => g.kind === "coil"))
        ) {
          const g = { ...p, kind };
          if (legal(g)) {
            onChange([...generators, g]);
            drag.current = generators.length;
            moved.current = true;
          }
        }
      }}
      onPointerMove={(e) => {
        if (drag.current === null || !e.buttons) return;
        const g = { ...generators[drag.current], ...point(e) };
        if (legal(g)) {
          moved.current = true;
          onChange(generators.map((a, i) => (i === drag.current ? g : a)));
        }
      }}
      onPointerUp={() => {
        drag.current = null;
      }}
    />
  );
}
