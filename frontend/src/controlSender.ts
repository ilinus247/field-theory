/** One pending control state, even during slow connections or rapid pointer input. */
export type SocketLike = {
  readyState: number;
  bufferedAmount: number;
  send: (data: string) => void;
};
export class ControlSender {
  private latest: unknown = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  constructor(
    privateSocket: () => SocketLike | null,
    privateCurrent: (data: any) => boolean,
    schedule: typeof setTimeout = setTimeout,
    cancel: typeof clearTimeout = clearTimeout,
  ) {
    this.socket = privateSocket;
    this.current = privateCurrent;
    this.schedule = schedule;
    this.cancel = cancel;
  }
  private socket: () => SocketLike | null;
  private current: (data: any) => boolean;
  private schedule: typeof setTimeout;
  private cancel: typeof clearTimeout;
  queue(data: unknown) {
    this.latest = data;
    this.arm();
  }
  private arm() {
    if (this.timer === undefined)
      this.timer = this.schedule(() => this.flush(), 80);
  }
  private flush() {
    this.timer = undefined;
    const socket = this.socket();
    if (!socket || socket.readyState !== 1 || !this.current(this.latest)) {
      this.latest = null;
      return;
    }
    // Do not fill the browser's outbound buffer with obsolete aim positions.
    if (socket.bufferedAmount > 8192) {
      this.arm();
      return;
    }
    const data = this.latest;
    this.latest = null;
    if (data !== null) socket.send(JSON.stringify(data));
  }
  reset() {
    if (this.timer !== undefined) this.cancel(this.timer);
    this.timer = undefined;
    this.latest = null;
  }
}
