import { useEffect, useRef, useState } from "react";
import { Calibration, getCalibration, previewCalibration, Settings } from "./api";
import SettingsPanel from "./SettingsPanel";
import { noteName } from "./notes";

interface Props {
  jobId: string;
  initialSettings: Settings;
  onConfirm: (cal: Calibration, settings: Settings) => void;
}

export default function CalibrationView({ jobId, initialSettings, onConfirm }: Props) {
  const [cal, setCal] = useState<Calibration | null>(null);
  const [settings, setSettings] = useState<Settings>(initialSettings);
  const [img, setImg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number>();

  useEffect(() => {
    getCalibration(jobId)
      .then((r) => {
        setCal(r.calibration);
        setSettings(r.settings);
      })
      .catch((e) => setError(e.message));
  }, [jobId]);

  // redraw the overlay a moment after the user stops editing
  useEffect(() => {
    if (!cal) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      previewCalibration(jobId, cal, settings)
        .then((u) => setImg((old) => (old && URL.revokeObjectURL(old), u)))
        .catch((e) => setError(e.message));
    }, 250);
    return () => window.clearTimeout(timer.current);
  }, [jobId, cal, settings]);

  if (!cal) return <div className="card">{error ? <p className="error">{error}</p> : "Loading…"}</div>;
  const set = (patch: Partial<Calibration>) => setCal({ ...cal, ...patch });
  const int = (k: keyof Calibration) => (
    <input type="number" value={cal[k] as number}
      onChange={(e) => set({ [k]: Math.round(Number(e.target.value)) } as Partial<Calibration>)} />
  );
  const hues = cal.hues ?? [];

  return (
    <div className="card">
      <h2>2. Check the detection</h2>
      <p className="muted">
        Yellow box = keyboard, small boxes = where each key is checked for a lit color (red = white keys, purple = black keys), swatches (top left) = hand colors. Every box should sit on its own key.
        Adjust anything that looks off; the preview updates.
      </p>
      {img ? <img className="preview" src={img} alt="Calibration preview" /> : <div className="preview placeholder">Rendering…</div>}
      <div className="grid">
        <label>Keyboard left (px){int("x0")}</label>
        <label>Keyboard right (px){int("x1")}</label>
        <label>Keyboard top (px){int("top")}</label>
        <label>Keyboard bottom (px){int("bottom")}</label>
        <label>White keys{int("n_white")}</label>
        <label>
          Leftmost key (MIDI) — {noteName(cal.first_midi)}
          {int("first_midi")}
        </label>
        {hues.map((h, i) => (
          <label key={i}>
            {i === 0 ? "Color 1" : "Color 2"} hue (°)
            <input type="number" min={0} max={360} value={h}
              onChange={(e) => set({ hues: hues.map((x, j) => (j === i ? Number(e.target.value) : x)) })} />
          </label>
        ))}
      </div>
      {hues.length === 2 && (
        <button type="button" onClick={() => set({ hues: [hues[0]] })}>
          Treat as one color (split hands by pitch)
        </button>
      )}
      <details>
        <summary>Settings</summary>
        <SettingsPanel value={settings} onChange={setSettings} />
      </details>
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={() => onConfirm(cal, settings)}>Convert to MIDI</button>
    </div>
  );
}
