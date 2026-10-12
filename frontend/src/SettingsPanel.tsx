import type { Settings } from "./api";

interface Props {
  value: Settings;
  onChange: (s: Settings) => void;
}

const num = (v: string): number | null => (v.trim() === "" || isNaN(Number(v)) ? null : Number(v));

/** The less common settings. Timing grid lives in TimingChips. */
export default function SettingsPanel({ value, onChange }: Props) {
  const set = (patch: Partial<Settings>) => onChange({ ...value, ...patch });
  return (
    <div className="grid">
      <label title="Only when snapping to a grid. Leave empty to detect the tempo automatically.">
        Tempo override (BPM)
        <input type="number" min={20} max={300} placeholder="auto" value={value.tempo_override ?? ""}
          disabled={value.quantize === "off"} onChange={(e) => set({ tempo_override: num(e.target.value) })} />
      </label>
      <label title="Used when the video has only one note color: notes at or above this pitch go to the right hand. 60 = middle C.">
        Hand split pitch (one-color videos)
        <input type="number" min={0} max={127} value={value.split_pitch} onChange={(e) => set({ split_pitch: num(e.target.value) ?? 60 })} />
      </label>
      <label>
        Note volume (1–127)
        <input type="number" min={1} max={127} value={value.velocity} onChange={(e) => set({ velocity: num(e.target.value) ?? 80 })} />
      </label>
      <label title="Ignore flickers shorter than this.">
        Shortest note (seconds)
        <input type="number" min={0} step={0.01} value={value.min_note_s} onChange={(e) => set({ min_note_s: num(e.target.value) ?? 0.05 })} />
      </label>
      <label>
        Start at (seconds)
        <input type="number" min={0} step={0.5} value={value.start_s} onChange={(e) => set({ start_s: num(e.target.value) ?? 0 })} />
      </label>
      <label>
        Stop at (seconds)
        <input type="number" min={0} step={0.5} placeholder="end of video" value={value.end_s ?? ""} onChange={(e) => set({ end_s: num(e.target.value) })} />
      </label>
    </div>
  );
}
