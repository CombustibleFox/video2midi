import { useRef, useState } from "react";
import { createJob, Settings } from "./api";
import SettingsPanel from "./SettingsPanel";
import TimingChips from "./TimingChips";

interface Props {
  settings: Settings;
  onSettings: (s: Settings) => void;
  onStarted: (id: string) => void;
}

const fmtSize = (b: number) => (b > 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${(b / 1e6).toFixed(1)} MB`);

export default function StartForm({ settings, onSettings, onStarted }: Props) {
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const pick = (f: File | undefined | null) => {
    if (!f) return;
    if (!f.type.startsWith("video/") && !/\.(mp4|mkv|mov|webm|avi|m4v)$/i.test(f.name)) {
      setError("That doesn't look like a video file. Try an .mp4, .mkv, .mov or .webm.");
      return;
    }
    setError(null);
    setFile(f);
    setUrl("");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const job = await createJob(file ? { file } : { url: url.trim() }, settings);
      onStarted(job.id);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <form className="card" onSubmit={submit}>
      <h2>Turn a piano video into MIDI</h2>

      <div
        className={"drop" + (over ? " over" : "") + (file ? " has" : "")}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
        onClick={() => input.current?.click()}
        role="button" tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.current?.click())}
      >
        <input ref={input} type="file" accept="video/*" hidden onChange={(e) => pick(e.target.files?.[0])} />
        {file ? (
          <>
            <strong>🎬 {file.name}</strong>
            <span className="muted">{fmtSize(file.size)} · <button type="button" className="link" onClick={(e) => { e.stopPropagation(); setFile(null); }}>remove</button></span>
          </>
        ) : (
          <>
            <strong>Drop a video here, or click to choose one</strong>
            <span className="muted">Falling-note piano videos (Synthesia style). 720p or higher works best.</span>
          </>
        )}
      </div>

      <div className="or"><span>or</span></div>
      <label>
        Paste a YouTube link
        <input type="url" placeholder="https://youtu.be/…" value={url} disabled={!!file} onChange={(e) => setUrl(e.target.value)} />
      </label>
      <p className="muted small">If YouTube refuses the download, save the video and drop the file above instead.</p>

      <fieldset>
        <legend>Timing</legend>
        <TimingChips value={settings} onChange={onSettings} />
      </fieldset>

      <details>
        <summary>More options</summary>
        <SettingsPanel value={settings} onChange={onSettings} />
      </details>

      {error && <p className="notice err" role="alert">{error}</p>}
      <button className="primary big" disabled={busy || (!file && !url.trim())}>
        {busy ? "Starting…" : "Analyse video →"}
      </button>

      <details className="tips">
        <summary>Tips for the best results</summary>
        <ul>
          <li>The whole keyboard should be visible at the bottom of the video.</li>
          <li>Use 720p or 1080p. Very small videos blur the gaps between repeated notes.</li>
          <li>You can fix the detected keyboard on the next step before converting.</li>
        </ul>
      </details>
    </form>
  );
}
