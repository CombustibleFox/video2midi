import { useEffect, useMemo, useRef, useState } from "react";
import { getResult, Result } from "./api";
import PianoRoll from "./PianoRoll";
import { Player } from "./player";

interface Props {
  jobId: string;
  onAdjust: () => void;
  onReset: () => void;
}

export default function ResultView({ jobId, onAdjust, onReset }: Props) {
  const [res, setRes] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [hands, setHands] = useState({ R: true, L: true });
  const player = useRef<Player | null>(null);

  useEffect(() => {
    getResult(jobId).then(setRes).catch((e) => setError(e.message));
  }, [jobId]);

  const duration = useMemo(() => (res?.notes.length ? Math.max(...res.notes.map((n) => n.end)) : 0), [res]);

  useEffect(() => {
    if (!res) return;
    player.current = new Player(res.notes, duration);
    return () => player.current?.stop();
  }, [res, duration]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      const p = player.current!;
      setTime(p.position);
      if (!p.playing || p.position >= duration) setPlaying(false);
      else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration]);

  if (!res) return <div className="card">{error ? <p className="error">{error}</p> : "Loading…"}</div>;
  const right = res.notes.filter((n) => n.hand === "R").length;

  const toggle = async () => {
    const p = player.current!;
    if (playing) {
      p.pause();
      setPlaying(false);
    } else {
      await p.play(time >= duration ? 0 : time, hands);
      setPlaying(true);
    }
  };
  const seek = async (t: number) => {
    const p = player.current!;
    setTime(t);
    if (playing) await p.play(t, hands);
    else p.stop(t);
  };

  return (
    <div className="card">
      <h2>3. Result</h2>
      <p>
        {res.notes.length} notes — <span className="r">{right} right hand</span>,{" "}
        <span className="l">{res.notes.length - right} left hand</span> — {res.bpm} BPM, {duration.toFixed(1)} s
      </p>
      <div className="row">
        <button className="primary" onClick={toggle} disabled={!res.notes.length}>{playing ? "Pause" : "Play"}</button>
        <button onClick={() => seek(0)}>Rewind</button>
        <label className="inline"><input type="checkbox" checked={hands.R}
          onChange={(e) => setHands({ ...hands, R: e.target.checked })} /> <span className="r">Right</span></label>
        <label className="inline"><input type="checkbox" checked={hands.L}
          onChange={(e) => setHands({ ...hands, L: e.target.checked })} /> <span className="l">Left</span></label>
        <a className="button" href={`/jobs/${jobId}/midi`} download="output.mid">Download .mid</a>
      </div>
      <p className="muted">Changing the hand checkboxes applies the next time you press Play.</p>
      {res.notes.length > 0 ? (
        <PianoRoll notes={res.notes} duration={duration} time={time} onSeek={seek} />
      ) : (
        <p className="error">No notes were detected. Go back and check the keyboard area and colors.</p>
      )}
      <div className="row">
        <button onClick={onAdjust}>Adjust detection / settings</button>
        <button onClick={onReset}>Start over</button>
      </div>
    </div>
  );
}
