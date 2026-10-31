import { test } from "node:test";
import assert from "node:assert/strict";
import { ControlSender } from "../src/controlSender.ts";
function setup() {
  let now = 0,
    next = 0;
  const timers = new Map(),
    sent = [];
  const socket = {
    readyState: 1,
    bufferedAmount: 0,
    send: (s) => sent.push(JSON.parse(s)),
  };
  const schedule = (fn, delay) => {
    const id = ++next;
    timers.set(id, { fn, time: now + delay });
    return id;
  };
  const cancel = (id) => timers.delete(id);
  const advance = (ms) => {
    const end = now + ms;
    for (;;) {
      const due = [...timers.entries()]
        .filter(([, t]) => t.time <= end)
        .sort((a, b) => a[1].time - b[1].time)[0];
      if (!due) break;
      now = due[1].time;
      timers.delete(due[0]);
      due[1].fn();
    }
    now = end;
  };
  return {
    socket,
    sent,
    advance,
    sender: new ControlSender(
      () => socket,
      () => true,
      schedule,
      cancel,
    ),
  };
}
test("continuous pointer input sends no more than 13 controls per second", () => {
  const x = setup();
  for (let i = 0; i < 1000; i++) {
    x.sender.queue({ angle: i });
    x.advance(1);
  }
  assert.ok(x.sent.length <= 13);
  x.advance(80);
  assert.equal(x.sent.at(-1).angle, 999);
});
test("backpressure retains only the latest controls instead of queuing network messages", () => {
  const x = setup();
  x.socket.bufferedAmount = 20000;
  for (let i = 0; i < 100; i++) {
    x.sender.queue({ angle: i });
    x.advance(10);
  }
  assert.equal(x.sent.length, 0);
  x.socket.bufferedAmount = 0;
  x.advance(80);
  assert.deepEqual(x.sent, [{ angle: 99 }]);
});
test("disconnect or ready reset cancels obsolete controls", () => {
  const x = setup();
  x.sender.queue({ angle: 1 });
  x.sender.reset();
  x.advance(1000);
  assert.deepEqual(x.sent, []);
  x.sender.queue({ angle: 2 });
  x.advance(80);
  assert.deepEqual(x.sent, [{ angle: 2 }]);
});

test("host timer functions are not called with the sender as their receiver", () => {
  let callback;
  let cancelled = false;
  const schedule = function (fn) {
    assert.equal(
      this,
      undefined,
      "browser timers reject a ControlSender receiver",
    );
    callback = fn;
    return 1;
  };
  const cancel = function () {
    assert.equal(
      this,
      undefined,
      "browser clearTimeout rejects a ControlSender receiver",
    );
    cancelled = true;
  };
  const sent = [];
  const socket = {
    readyState: 1,
    bufferedAmount: 0,
    send: (m) => sent.push(JSON.parse(m)),
  };
  const sender = new ControlSender(
    () => socket,
    () => true,
    schedule,
    cancel,
  );
  sender.queue({ angle: 1 });
  callback();
  assert.deepEqual(sent, [{ angle: 1 }]);
  sender.queue({ angle: 2 });
  sender.reset();
  assert.equal(cancelled, true);
});
