import type { JobState } from "./api";

const LABELS: Record<string, string> = {
  queued: "Queued",
  downloading: "Downloading",
  calibrating: "Analysing keyboard",
  extracting: "Reading notes",
  exporting: "Writing MIDI",
};

export default function Progress({ job }: { job: JobState | null }) {
  const pct = Math.round((job?.progress ?? 0) * 100);
  return (
    <div className="card">
      <h2>{LABELS[job?.status ?? "queued"] ?? job?.status}…</h2>
      <div className="bar"><div style={{ width: `${pct}%` }} /></div>
      <p className="muted">{job?.message} {pct > 0 && `(${pct}%)`}</p>
    </div>
  );
}
