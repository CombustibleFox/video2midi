import { useEffect, useRef, useState } from "react";
import { Calibration, getCalibration, previewCalibration, Settings } from "./api";
import ClipDownload from "./ClipDownload";
import SettingsPanel from "./SettingsPanel";
import TimingChips from "./TimingChips";
import { lastMidi, noteName } from "./notes";

interface Props {
  jobId: string;
  initialSettings: Settings;
  onConfirm: (cal: Calibration, settings: Settings) => void;
  onBack: () => void;
}

export default function CalibrationView({ jobId, initialSettings, onConfirm, onBack }: Props) {
  const [detected, setDetected] = useState<Calibration | null>(null);
  const [cal, setCal] = useState<Calibration | null>(null);
  const [settings, setSettings] = useState<Settings>(initialSettings);
  const [img, setImg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adjust, setAdjust] = useState(false);
  const timer = useRef<number>();

  useEffect(() => {
    getCalibration(jobId)
      .then((r) => {
        setDetected(r.calibration);
        setCal(r.calibration);
        setSettings((s) => ({ ...r.settings, quantize: s.quantize, tempo_override: s.tempo_override }));
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

  if (!cal || !detected) return <div className="card">{error ? <p className="notice err">{error}</p> : <p className="muted">Loading…</p>}</div>;

  const set = (patch: Partial<Calibration>) => setCal({ ...cal, ...patch });
  const int = (k: keyof Calibration) => (
    <input type="number" value={cal[k] as number} onChange={(e) => set({ [k]: Math.round(Number(e.target.value)) } as Partial<Calibration>)} />
  );
  const hues = cal.hues ?? [];
  const changed = JSON.stringify(cal) !== JSON.stringify(detected);

  return (
    <div className="card">
      <h2>Does this look right?</h2>
      <p className="muted">
        The small boxes should sit on the piano keys, and the colored squares in the corner should match your two note colors.
      </p>

      <ul className="facts">
        <li><b>{cal.n_white}</b> white keys</li>
        <li><b>{noteName(cal.first_midi)}</b> to <b>{noteName(lastMidi(cal.first_midi, cal.n_white))}</b></li>
        <li>
          {hues.length > 1 ? "2 note colors" : "1 note color"}{" "}
          {hues.map((h, i) => <i key={i} className="hue" style={{ background: `hsl(${h} 75% 55%)` }} title={`hue ${Math.round(h)}°`} />)}
        </li>
        <li>{cal.width}×{cal.height}</li>
      </ul>

      {img ? <img className="preview" src={img} alt="The detected keyboard drawn over a video frame" /> : <div className="preview placeholder">Drawing…</div>}

      <div className="timing-row">
        <strong>Timing</strong>
        <TimingChips value={settings} onChange={setSettings} />
      </div>

      {error && <p className="notice err" role="alert">{error}</p>}
      <div className="row">
        <button className="primary big" onClick={() => onConfirm(cal, settings)}>Looks right — convert →</button>
        <button type="button" onClick={() => setAdjust(!adjust)} aria-expanded={adjust}>{adjust ? "Hide adjustments" : "Something's off?"}</button>
        <button type="button" className="link" onClick={onBack}>← Choose a different video</button>
      </div>

      {adjust && (
        <section className="adjust">
          <h3>Adjust the detection</h3>
          <p className="muted">Change a value and the picture above updates. If the pitches are all shifted, fix “leftmost key”.</p>
          <div className="grid">
            <label>Keyboard left (px){int("x0")}</label>
            <label>Keyboard right (px){int("x1")}</label>
            <label>Keyboard top (px){int("top")}</label>
            <label>Keyboard bottom (px){int("bottom")}</label>
            <label>White keys{int("n_white")}</label>
            <label>Leftmost key (MIDI number, now {noteName(cal.first_midi)}){int("first_midi")}</label>
            {hues.map((h, i) => (
              <label key={i}>
                Note color {i + 1} (hue, degrees)
                <input type="number" min={0} max={360} value={h} onChange={(e) => set({ hues: hues.map((x, j) => (j === i ? Number(e.target.value) : x)) })} />
              </label>
            ))}
          </div>
          <div className="row">
            {hues.length === 2 && <button type="button" onClick={() => set({ hues: [hues[0]] })}>Treat as one color (split hands by pitch)</button>}
            {changed && <button type="button" onClick={() => setCal(detected)}>Reset to what was detected</button>}
          </div>
        </section>
      )}

      <details>
        <summary>More options</summary>
        <SettingsPanel value={settings} onChange={setSettings} />
      </details>
      <ClipDownload jobId={jobId} />
    </div>
  );
}
