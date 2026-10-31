import { useEffect, useRef } from "react";
export function Rules({ close }: { close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={close}
      aria-labelledby="rules-title"
      className="rules"
    >
      <button
        className="rules-close"
        onClick={close}
        aria-label="close rules"
        autoFocus
      >
        ×
      </button>
      <div className="eyebrow">A FIELD GUIDE</div>
      <h2 id="rules-title">Keep the stream flowing.</h2>
      <p>
        Three rounds. Eight seconds to set up, then sixty seconds of live play.
        Your cannon fires automatically. Aim and move, add, or remove your own
        fields throughout the round.
      </p>
      <h3>Control your corner</h3>
      <p>
        Select a charge or coil and tap the arena to place it. Drag a field to
        move it; use its × button to remove it. Choose <b>aim cannon</b> to aim
        by dragging anywhere in the arena, or use the angle slider. You have two
        field slots, including at most one coil. Protected reactor circles stay
        clear.
      </p>
      <p>
        Red repels. Blue attracts. Purple curves moving particles. All players
        share the fields. Opposing positive streams also repel one another. Your
        objects have a solid dark outline and a <b>you</b> label; numbered
        badges match each player’s reactor.
      </p>
      <h3>Score sustained contact</h3>
      <p>
        Keep your stream hitting opposing reactors to earn pressure seconds.
        Brief gaps of up to 0.23 seconds between particles count as continuous
        contact. Hitting yourself scores nothing. Scores accumulate across three
        rounds; equal scores share the win.
      </p>
      <h3>Hit the labeled boosters</h3>
      <p>
        A pickup appears after six seconds, then about every eight seconds. Hit
        it with a particle to collect it. Pickups expire after ten seconds;
        effects last six seconds and refresh instead of stacking.
      </p>
      <div className="booster-rules">
        <div>
          <h4>benefits for you</h4>
          <p>
            <b>rapid fire</b> — twice the particles
            <br />
            <b>double score</b> — twice the pressure points
            <br />
            <b>shield</b> — incoming streams cannot score
          </p>
        </div>
        <div>
          <h4>disrupt your rivals</h4>
          <p>
            <b>slow rivals</b> — half their firing rate
            <br />
            <b>weak fields</b> — their generators drop to 45% strength
            <br />
            <b>aim drift</b> — their cannon direction gently wobbles
          </p>
        </div>
      </div>
      <p className="fine">
        The server calculates motion, pickups, and scores. A disconnected cannon
        stops firing. Rooms disappear after server restarts. The host can start
        a rematch after the final round.
      </p>
      <button className="primary" onClick={close}>
        back to the field ↗
      </button>
    </dialog>
  );
}
