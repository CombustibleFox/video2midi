import { useState } from "react";
import { createJob, DEFAULT_SETTINGS, Settings } from "./api";
import SettingsPanel from "./SettingsPanel";

interface Props {
  onStarted: (id: string, settings: Settings) => void;
}

export default function StartForm({ onStarted }: Props) {
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const job = await createJob(file ? { file } : { url: url.trim() }, settings);
      onStarted(job.id, settings);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <form className="card" onSubmit={submit}>
      <h2>1. Choose a video</h2>
      <label>
        YouTube URL
        <input type="url" placeholder="https://youtu.be/…" value={url} disabled={!!file}
          onChange={(e) => setUrl(e.target.value)} />
      </label>
      <p className="muted center">or upload a file (use this if YouTube blocks the download)</p>
      <label>
        Video file
        <input type="file" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <details>
        <summary>Settings</summary>
        <SettingsPanel value={settings} onChange={setSettings} />
      </details>
      {error && <p className="error">{error}</p>}
      <button className="primary" disabled={busy || (!file && !url.trim())}>
        {busy ? "Starting…" : "Analyse video"}
      </button>
    </form>
  );
}
