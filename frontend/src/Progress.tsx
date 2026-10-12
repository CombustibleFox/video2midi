import type { JobState } from "./api";
import Mascot from "./Mascot";
import type { ThemeInfo } from "./themes";

const STAGES: [string, string][] = [
  ["downloading", "Download"],
  ["calibrating", "Find keyboard"],
  ["extracting", "Read notes"],
  ["exporting", "Write MIDI"],
];

const TITLES: Record<string, string> = {
  queued: "Getting ready",
  downloading: "Downloading the video",
  calibrating: "Looking for the keyboard",
  extracting: "Reading the notes",
  exporting: "Writing the MIDI file",
};

export default function Progress({ job, theme }: { job: JobState | null; theme: ThemeInfo }) {
  const pct = Math.round((job?.progress ?? 0) * 100);
  const status = job?.status ?? "queued";
  const at = STAGES.findIndex(([s]) => s === status);
  return (
    <div className="card progress" role="status" aria-live="polite">
      <h2>{TITLES[status] ?? status}…</h2>
      <div className={"track" + (theme.playful ? " playful" : "")}>
        <div className="fill" style={{ width: `${pct}%` }} />
        {theme.playful && (
          <div className="rider" style={{ left: `${pct}%` }}><Mascot kind={theme.playful} size={44} /></div>
        )}
      </div>
      <p className="muted">{job?.message} {pct > 0 && <strong>{pct}%</strong>}</p>
      <ul className="stages">
        {STAGES.map(([s, label], i) => (
          <li key={s} className={i < at ? "done" : i === at ? "now" : ""}>{i < at ? "✓ " : ""}{label}</li>
        ))}
      </ul>
    </div>
  );
}
