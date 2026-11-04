import { centers, colors, type ArenaSetup } from "./types";

/** A map thumbnail of the real fixture and reactor positions, without simulated paths. */
export function ArenaPreview({
  arena,
  players,
}: {
  arena: ArenaSetup;
  players: number;
}) {
  return (
    <svg viewBox="0 0 160 104" aria-hidden="true" className="arena-thumbnail">
      <rect
        x="1"
        y="1"
        width="158"
        height="102"
        rx="6"
        fill="#f7f8f1"
        stroke="#b7beaa70"
      />
      <path
        d="M40 2V102M80 2V102M120 2V102M2 26H158M2 52H158M2 78H158"
        stroke="#8c987b12"
      />
      {centers(Math.max(2, players)).map(([x, y], i) => (
        <g key={i}>
          <ellipse
            cx={x * 160}
            cy={y * 104}
            rx="12"
            ry="8"
            fill="none"
            stroke={colors[i] + "40"}
            strokeDasharray="2 3"
          />
          <circle cx={x * 160} cy={y * 104} r="3.5" fill={colors[i]} />
        </g>
      ))}
      {arena.objects.map((o, i) => (
        <g key={i}>
          <ellipse
            cx={o.x * 160}
            cy={o.y * 104}
            rx={o.radius * 160}
            ry={o.radius * 104}
            fill={o.kind === "lens" ? "#618a9b14" : "#967bb414"}
            stroke={o.kind === "lens" ? "#618a9b99" : "#967bb499"}
            strokeDasharray="2 2"
          />
          <text
            x={o.x * 160}
            y={o.y * 104 + 4}
            textAnchor="middle"
            fontSize="13"
            fill={o.kind === "lens" ? "#567e90" : "#87669f"}
          >
            {o.kind === "lens" ? "◎" : o.strength > 0 ? "↺" : "↻"}
          </text>
        </g>
      ))}
    </svg>
  );
}
