import { useState } from "react";
import { clipUrl, downloadFile, frameUrl } from "./api";

interface Props {
  jobId: string;
  /** Start suggested by the caller (video seconds), e.g. the playhead position. */
  suggestedStart?: number;
  /** Seconds to add to piano-roll time to get video time. */
  offset?: number;
  playhead?: number;
}

const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;

export default function ClipDownload({ jobId, suggestedStart = 0, offset, playhead }: Props) {
  const [start, setStart] = useState(suggestedStart);
  const [length, setLength] = useState(25);
  const [busy, setBusy] = useState<"clip" | "frame" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (kind: "clip" | "frame") => {
    setError(null);
    setBusy(kind);
    try {
      if (kind === "clip") await downloadFile(clipUrl(jobId, start, length), `clip_${Math.round(start)}s.mp4`);
      else await downloadFile(frameUrl(jobId, start), `frame_${start.toFixed(1)}s.png`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const usePlayhead = () => {
    if (playhead === undefined || offset === undefined) return;
    setStart(Math.max(0, Math.round((playhead + offset - 1) * 10) / 10)); // start a second before
  };

  return (
    <details className="clipbox">
      <summary>Save a clip or frame of the original video (for sharing a problem spot)</summary>
      <div className="grid">
        <label>
          Video time (seconds)
          <input type="number" min={0} step={0.1} value={start}
            onChange={(e) => setStart(Math.max(0, Number(e.target.value) || 0))} />
        </label>
        <label>
          Clip length (seconds, max 60)
          <input type="number" min={1} max={60} value={length}
            onChange={(e) => setLength(Math.min(60, Math.max(1, Number(e.target.value) || 25)))} />
        </label>
      </div>
      <p className="muted">
        Starts at {fmt(start)} in the video.
        {offset !== undefined && ` The piano roll starts ${offset.toFixed(1)} s into the video, so a note at roll time T is at video time T + ${offset.toFixed(1)}.`}
      </p>
      <div className="row">
        {playhead !== undefined && offset !== undefined && (
          <button type="button" onClick={usePlayhead}>Use playhead (1 s earlier)</button>
        )}
        <button type="button" disabled={busy !== null} onClick={() => run("clip")}>
          {busy === "clip" ? "Cutting clip…" : "Download clip (.mp4)"}
        </button>
        <button type="button" disabled={busy !== null} onClick={() => run("frame")}>
          {busy === "frame" ? "Grabbing frame…" : "Download frame (.png)"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </details>
  );
}
