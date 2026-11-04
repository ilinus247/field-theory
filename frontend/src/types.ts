export type Generator = {
  kind: "positive" | "negative" | "coil";
  x: number;
  y: number;
};
export type Player = {
  id: string;
  name: string;
  score: number;
  ready: boolean;
  connected: boolean;
  angle: number;
  generators: Generator[];
  effects: Record<string, number>;
};
export type Particle = [number, number, number, number];
export type Live = {
  time: number;
  particles: Particle[];
  contact: boolean[][];
  scores: number[];
  interactions: boolean;
};
export type Booster = {
  id: string;
  kind: string;
  label: string;
  target: "self" | "rivals";
  x: number;
  y: number;
  expires: number;
};
export type ArenaSetup = {
  id: string;
  name: string;
  description: string;
  objects: {
    kind: "lens" | "vortex";
    label: string;
    x: number;
    y: number;
    radius: number;
    strength: number;
  }[];
};
export type State = {
  arena?: ArenaSetup;
  arenas?: ArenaSetup[];
  code: string;
  players: Player[];
  phase: string;
  round: number;
  match: number;
  seq: number;
  deadline: number | null;
  host: string;
  server_time: number;
  live: Live | null;
  boosters: Booster[];
  notices: { text: string; until: number }[];
  rules: { rounds: number; setup_seconds: number; live_seconds: number };
};
export const centers = (n: number): [number, number][] =>
  n === 2
    ? [
        [0.12, 0.5],
        [0.88, 0.5],
      ]
    : n === 3
      ? [
          [0.12, 0.5],
          [0.69, 0.1709103465619133],
          [0.69, 0.8290896534380867],
        ]
      : [
          [0.12, 0.18],
          [0.88, 0.18],
          [0.88, 0.82],
          [0.12, 0.82],
        ];
export const colors = ["#b86550", "#487d9c", "#8567a8", "#7f873f"];
export const effectNames: Record<string, string> = {
  rapid: "rapid fire",
  power: "double score",
  shield: "shield",
  slow: "slow fire",
  weaken: "weak fields",
  drift: "aim drift",
};
