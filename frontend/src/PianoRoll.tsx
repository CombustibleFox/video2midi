import { useEffect, useRef } from "react";
import type { NoteOut } from "./api";
import { isBlack } from "./notes";

interface Props {
  notes: NoteOut[];
  duration: number;
  time: number; // playhead, seconds
  onSeek: (t: number) => void;
}

const PX_PER_SEC = 80;
const ROW = 7;

export default function PianoRoll({ notes, duration, time, onSeek }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const lo = Math.min(...notes.map((n) => n.pitch), 60) - 1;
  const hi = Math.max(...notes.map((n) => n.pitch), 60) + 1;
  const width = Math.max(600, Math.ceil(duration * PX_PER_SEC) + 20);
  const height = (hi - lo + 1) * ROW;
  const y = (p: number) => (hi - p) * ROW;

  useEffect(() => {
    const c = canvas.current!;
    const g = c.getContext("2d")!;
    g.clearRect(0, 0, width, height);
    for (let p = lo; p <= hi; p++) {
      g.fillStyle = isBlack(p) ? "#1b1f27" : "#232833";
      g.fillRect(0, y(p), width, ROW);
      if (p % 12 === 0) {
        g.fillStyle = "#3b4252";
        g.fillRect(0, y(p) + ROW - 1, width, 1);
      }
    }
    for (const n of notes) {
      g.fillStyle = n.hand === "R" ? "#4cc38a" : "#5b9dff";
      g.fillRect(n.start * PX_PER_SEC, y(n.pitch) + 1, Math.max(2, (n.end - n.start) * PX_PER_SEC - 1), ROW - 2);
    }
  }, [notes, width, height]);

  // keep the playhead in view while playing
  useEffect(() => {
    const w = wrap.current;
    if (!w) return;
    const x = time * PX_PER_SEC;
    if (x < w.scrollLeft || x > w.scrollLeft + w.clientWidth - 40) w.scrollLeft = Math.max(0, x - 40);
  }, [time]);

  return (
    <div className="roll" ref={wrap}>
      <div style={{ position: "relative", width, height }}
        onClick={(e) => onSeek(Math.max(0, (e.clientX - e.currentTarget.getBoundingClientRect().left) / PX_PER_SEC))}>
        <canvas ref={canvas} width={width} height={height} />
        <div className="playhead" style={{ left: time * PX_PER_SEC }} />
      </div>
    </div>
  );
}
