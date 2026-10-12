export interface Settings {
  quantize: string;
  tempo_override: number | null;
  variable_tempo: boolean;
  split_pitch: number;
  min_note_s: number;
  gap_fill_frames: number;
  velocity: number;
  start_s: number;
  end_s: number | null;
  hit_offset: number;
  trim_to_first_note: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  quantize: "1/32",
  tempo_override: null,
  variable_tempo: true,
  split_pitch: 60,
  min_note_s: 0.05,
  gap_fill_frames: 1,
  velocity: 80,
  start_s: 0,
  end_s: null,
  hit_offset: 4,
  trim_to_first_note: true,
};

export interface Calibration {
  width: number;
  height: number;
  fps: number;
  frame_count: number;
  x0: number;
  x1: number;
  top: number;
  bottom: number;
  n_white: number;
  first_midi: number;
  hues: number[] | null;
  key_hues?: number[] | null;
}

export interface JobState {
  id: string;
  status: string;
  progress: number;
  message: string;
  error: string | null;
  version: number;
}

export interface NoteOut {
  pitch: number;
  start: number;
  end: number;
  hand: "R" | "L";
}

export interface Result {
  title?: string | null;
  file_stem?: string; // the video's name as a safe file name
  bpm: number;
  tempo_map?: { time: number; beat: number; bpm: number }[];
  video_offset: number; // video time of the first note: video time = piano-roll time + this
  notes: NoteOut[];
}

async function check(r: Response) {
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const body = await r.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not json */
    }
    throw new Error(msg);
  }
  return r;
}

export async function createJob(
  src: { url: string } | { file: File },
  settings: Settings,
): Promise<JobState> {
  if ("url" in src) {
    const r = await fetch("/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: src.url, settings }),
    });
    return (await check(r)).json();
  }
  const form = new FormData();
  form.append("file", src.file);
  form.append("settings", JSON.stringify(settings));
  const r = await fetch("/jobs", { method: "POST", body: form });
  return (await check(r)).json();
}

export async function getCalibration(id: string): Promise<{ calibration: Calibration; settings: Settings }> {
  return (await check(await fetch(`/jobs/${id}/calibration`))).json();
}

export async function previewCalibration(id: string, calibration: Partial<Calibration>, settings: Partial<Settings>): Promise<string> {
  const r = await check(
    await fetch(`/jobs/${id}/calibration/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ calibration, settings }),
    }),
  );
  return URL.createObjectURL(await r.blob());
}

export async function processJob(id: string, calibration: Calibration, settings: Settings): Promise<JobState> {
  const r = await fetch(`/jobs/${id}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ calibration, settings }),
  });
  return (await check(r)).json();
}

export async function getResult(id: string): Promise<Result> {
  return (await check(await fetch(`/jobs/${id}/notes`))).json();
}

export async function deleteJob(id: string) {
  await fetch(`/jobs/${id}`, { method: "DELETE" }).catch(() => undefined);
}

/** Download a file from the server and hand it to the browser as a save-as. */
export async function downloadFile(url: string, filename: string): Promise<void> {
  const r = await check(await fetch(url));
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}

export const clipUrl = (id: string, start: number, duration: number) =>
  `/jobs/${id}/clip?start=${start}&duration=${duration}`;
export const frameUrl = (id: string, t: number) => `/jobs/${id}/frame?t=${t}`;

export const midiUrl = (id: string, hand: "both" | "R" | "L" = "both") => `/jobs/${id}/midi?hand=${hand}`;
