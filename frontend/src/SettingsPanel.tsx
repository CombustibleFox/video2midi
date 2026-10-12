import type { Settings } from "./api";

interface Props {
  value: Settings;
  onChange: (s: Settings) => void;
}

const num = (v: string): number | null => (v.trim() === "" || isNaN(Number(v)) ? null : Number(v));

export default function SettingsPanel({ value, onChange }: Props) {
  const set = (patch: Partial<Settings>) => onChange({ ...value, ...patch });
  return (
    <div className="grid">
      <label>
        Quantize
        <select value={value.quantize} onChange={(e) => set({ quantize: e.target.value })}>
          <option value="1/4">Quarter notes</option>
          <option value="1/8">Eighth notes</option>
          <option value="1/16">Sixteenth notes</option>
          <option value="1/32">Thirty-second notes</option>
          <option value="off">Off (exact timing, 120 BPM)</option>
        </select>
      </label>
      <label>
        Tempo override (BPM)
        <input type="number" min={20} max={300} placeholder="auto" value={value.tempo_override ?? ""}
          disabled={value.quantize === "off"}
          onChange={(e) => set({ tempo_override: num(e.target.value) })} />
      </label>
      <label>
        Split pitch (one-color videos)
        <input type="number" min={0} max={127} value={value.split_pitch}
          onChange={(e) => set({ split_pitch: num(e.target.value) ?? 60 })} />
      </label>
      <label>
        Velocity
        <input type="number" min={1} max={127} value={value.velocity}
          onChange={(e) => set({ velocity: num(e.target.value) ?? 80 })} />
      </label>
      <label>
        Min note length (s)
        <input type="number" min={0} step={0.01} value={value.min_note_s}
          onChange={(e) => set({ min_note_s: num(e.target.value) ?? 0.05 })} />
      </label>
      <label>
        Start (s)
        <input type="number" min={0} step={0.5} value={value.start_s}
          onChange={(e) => set({ start_s: num(e.target.value) ?? 0 })} />
      </label>
      <label>
        End (s)
        <input type="number" min={0} step={0.5} placeholder="end of video" value={value.end_s ?? ""}
          onChange={(e) => set({ end_s: num(e.target.value) })} />
      </label>
    </div>
  );
}
