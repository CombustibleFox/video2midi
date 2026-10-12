import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { NoteOut } from "./api";
import { isBlack, noteName } from "./notes";
import { themeColor } from "./themes";

interface Props {
  notes: NoteOut[];
  duration: number;
  time: number; // playhead, seconds
  zoom: number; // pixels per second
  themeId: string; // redraw when the theme changes
  colors?: { R: string; L: string } | null; // hand colors from the video; the theme's colors when absent
  onSeek: (t: number) => void;
}

/** Piano roll drawn only for the visible window, so long pieces stay sharp at any zoom. */
export default function PianoRoll({ notes, duration, zoom, time, themeId, colors, onSeek }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [scroll, setScroll] = useState(0);
  const [viewW, setViewW] = useState(800);
  const leftTime = useRef(0); // time at the left edge, so zooming keeps your place

  const lo = Math.min(...notes.map((n) => n.pitch), 60) - 1;
  const hi = Math.max(...notes.map((n) => n.pitch), 60) + 1;
  const row = Math.max(5, Math.min(11, Math.floor(280 / (hi - lo + 1))));
  const height = (hi - lo + 1) * row;
  const total = Math.max(viewW, Math.ceil(duration * zoom) + 40);
  const y = (p: number) => (hi - p) * row;

  useLayoutEffect(() => {
    const el = scroller.current;
    if (el) el.scrollLeft = leftTime.current * zoom;
  }, [zoom]);

  useEffect(() => {
    const el = scroller.current!;
    const ro = new ResizeObserver(() => setViewW(el.clientWidth));
    ro.observe(el);
    setViewW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current!;
    const dpr = window.devicePixelRatio || 1;
    c.width = viewW * dpr;
    c.height = height * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    const rowA = themeColor("--roll-a", "#232833"), rowB = themeColor("--roll-b", "#1b1f27");
    const octave = themeColor("--roll-octave", "#3b4252");
    const right = colors?.R ?? themeColor("--right", "#4cc38a"), left = colors?.L ?? themeColor("--left", "#5b9dff");
    const edge = themeColor("--roll-edge", "transparent");
    g.clearRect(0, 0, viewW, height);
    for (let p = lo; p <= hi; p++) {
      g.fillStyle = isBlack(p) ? rowB : rowA;
      g.fillRect(0, y(p), viewW, row);
      if (p % 12 === 0) {
        g.fillStyle = octave;
        g.fillRect(0, y(p) + row - 1, viewW, 1);
      }
    }
    const t0 = scroll / zoom, t1 = (scroll + viewW) / zoom;
    for (const n of notes) {
      if (n.end < t0 || n.start > t1) continue;
      const x = n.start * zoom - scroll;
      const w = Math.max(2, (n.end - n.start) * zoom - 1);
      g.fillStyle = n.hand === "R" ? right : left;
      g.fillRect(x, y(n.pitch) + 1, w, row - 2);
      if (edge !== "transparent") {
        g.strokeStyle = edge;
        g.strokeRect(x + 0.5, y(n.pitch) + 1.5, Math.max(1, w - 1), row - 3);
      }
    }
  }, [notes, zoom, scroll, viewW, height, lo, hi, row, themeId, colors?.R, colors?.L]);

  // keep the playhead in view while playing
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const x = time * zoom;
    if (x < el.scrollLeft || x > el.scrollLeft + el.clientWidth - 60) el.scrollLeft = Math.max(0, x - 60);
  }, [time, zoom]);

  const labels = [];
  for (let p = lo; p <= hi; p++) if (p % 12 === 0) labels.push(p);

  return (
    <div className="roll-wrap">
      <div className="gutter" style={{ height }}>
        {labels.map((p) => (
          <span key={p} style={{ top: y(p) + row / 2 - 6 }}>{noteName(p)}</span>
        ))}
      </div>
      <div className="roll" ref={scroller} onScroll={(e) => { leftTime.current = e.currentTarget.scrollLeft / zoom; setScroll(e.currentTarget.scrollLeft); }}>
        <div className="roll-inner" style={{ width: total, height }}
          onClick={(e) => {
            const r = scroller.current!.getBoundingClientRect();
            onSeek(Math.max(0, (e.clientX - r.left + scroller.current!.scrollLeft) / zoom));
          }}>
          <canvas ref={canvas} style={{ width: viewW, height }} />  {/* sticky at left:0 (see CSS): it stays put while the notes scroll under it */}
          <div className="playhead" style={{ left: time * zoom }} />
        </div>
      </div>
    </div>
  );
}
