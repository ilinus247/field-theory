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
};
export type Playback = {
  frames: ([number, number] | null)[][];
  frame_dt: number;
  duration: number;
  start: number;
  events: {
    owner: string;
    target: string;
    scored: boolean;
    time: number;
    x: number;
    y: number;
  }[];
};
export type State = {
  code: string;
  players: Player[];
  phase: string;
  round: number;
  match: number;
  seq: number;
  deadline: number | null;
  host: string;
  server_time: number;
  playback: Playback | null;
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
export const colors = ["#c77460", "#658da8", "#9482b2", "#9b9e62"];
