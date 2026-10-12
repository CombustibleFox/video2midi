import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getResult, midiUrl, Result } from "./api";
import ClipDownload from "./ClipDownload";
import PianoRoll from "./PianoRoll";
import { Player } from "./player";
import { fmtTime } from "./notes";

interface Props {
  jobId: string;
  themeId: string;
  onAdjust: () => void;
  onReset: () => void;
}

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5];

export default function ResultView({ jobId, themeId, onAdjust, onReset }: Props) {
  const [res, setRes] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [hands, setHands] = useState({ R: true, L: true });
  const [rate, setRate] = useState(1);
  const [zoom, setZoom] = useState(80);
  const player = useRef<Player | null>(null);

  useEffect(() => {
    getResult(jobId).then(setRes).catch((e) => setError(e.message));
  }, [jobId]);

  const duration = useMemo(() => (res?.notes.length ? Math.max(...res.notes.map((n) => n.end)) : 0), [res]);
  const counts = useMemo(() => {
    const r = res?.notes.filter((n) => n.hand === "R").length ?? 0;
    return { R: r, L: (res?.notes.length ?? 0) - r };
  }, [res]);

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

  const toggle = useCallback(async () => {
    const p = player.current;
    if (!p || !duration) return;
    if (playing) {
      p.pause();
      setPlaying(false);
    } else {
      await p.play(time >= duration ? 0 : time, hands, rate);
      setPlaying(true);
    }
  }, [playing, time, duration, hands, rate]);

  const seek = useCallback(async (t: number) => {
    const p = player.current;
    if (!p) return;
    const clamped = Math.min(Math.max(0, t), duration);
    setTime(clamped);
    if (playing) await p.play(clamped, hands, rate);
    else p.stop(clamped);
  }, [playing, hands, rate, duration]);

  // changing hands or speed while playing takes effect immediately
  const restartWith = async (nextHands = hands, nextRate = rate) => {
    if (playing && player.current) await player.current.play(player.current.position, nextHands, nextRate);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (/^(INPUT|SELECT|TEXTAREA|BUTTON|SUMMARY|A)$/.test(el.tagName)) return;
      if (e.code === "Space") { e.preventDefault(); toggle(); }
      else if (e.code === "ArrowLeft") seek(time - 2);
      else if (e.code === "ArrowRight") seek(time + 2);
      else if (e.code === "Home") seek(0);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, seek, time]);

  if (!res) return <div className="card">{error ? <p className="notice err">{error}</p> : <p className="muted">Loading…</p>}</div>;

  const flip = (h: "R" | "L") => {
    const next = { ...hands, [h]: !hands[h] };
    setHands(next);
    restartWith(next);
  };

  return (
    <div className="card result">
      <h2>Your MIDI is ready 🎉</h2>

      <ul className="stats">
        <li><b>{res.notes.length}</b><span>notes</span></li>
        <li className="r"><b>{counts.R}</b><span>right hand</span></li>
        <li className="l"><b>{counts.L}</b><span>left hand</span></li>
        <li><b>{res.bpm}</b><span>BPM</span></li>
        <li><b>{fmtTime(duration)}</b><span>length</span></li>
      </ul>

      <div className="downloads">
        <a className="button primary big" href={midiUrl(jobId)} download="output.mid">⬇ Download MIDI</a>
        <span className="muted small">Both hands on separate tracks. Or just one:</span>
        <a className="button" href={midiUrl(jobId, "R")} download="right_hand.mid">Right hand only</a>
        <a className="button" href={midiUrl(jobId, "L")} download="left_hand.mid">Left hand only</a>
      </div>

      {res.notes.length > 0 ? (
        <>
          <div className="transport">
            <button className="primary" onClick={toggle} aria-label={playing ? "Pause" : "Play"}>{playing ? "⏸ Pause" : "▶ Play"}</button>
            <button onClick={() => seek(0)} aria-label="Back to the start">⏮</button>
            <span className="clock" aria-live="off">{fmtTime(time)} / {fmtTime(duration)}</span>
            <span className="spacer" />
            <button type="button" className={"chip r" + (hands.R ? " on" : "")} aria-pressed={hands.R} onClick={() => flip("R")}>Right hand</button>
            <button type="button" className={"chip l" + (hands.L ? " on" : "")} aria-pressed={hands.L} onClick={() => flip("L")}>Left hand</button>
            <label className="inline">Speed
              <select value={rate} onChange={(e) => { const r = Number(e.target.value); setRate(r); restartWith(hands, r); }}>
                {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
              </select>
            </label>
          </div>
          <PianoRoll notes={res.notes} duration={duration} time={time} zoom={zoom} themeId={themeId} onSeek={seek} />
          <div className="roll-tools">
            <label className="inline">Zoom
              <input type="range" min={30} max={200} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} />
            </label>
            <span className="muted small">Click the roll to jump · Space plays/pauses · ←/→ skip 2 s</span>
          </div>
        </>
      ) : (
        <p className="notice err">No notes were found. Go back and check the keyboard area and note colors.</p>
      )}

      <div className="row">
        <button onClick={onAdjust}>Adjust detection or timing</button>
        <button onClick={onReset}>Convert another video</button>
      </div>
      <ClipDownload jobId={jobId} offset={res.video_offset} playhead={time}
        suggestedStart={Math.max(0, Math.round((res.video_offset - 1) * 10) / 10)} />
    </div>
  );
}
