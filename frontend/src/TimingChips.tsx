import type { Settings } from "./api";

const OPTIONS: { value: string; label: string; hint: string }[] = [
  { value: "1/32", label: "Snap to 1/32", hint: "Tidy rhythm for sheet music apps. Finest grid, keeps fast notes." },
  { value: "1/16", label: "1/16", hint: "Tidier, but fast ornaments get nudged." },
  { value: "1/8", label: "1/8", hint: "Very tidy; only for simple rhythms." },
  { value: "off", label: "Exact timing", hint: "Keep the video's exact timing (fixed 120 BPM)." },
];

export default function TimingChips({ value, onChange }: { value: Settings; onChange: (s: Settings) => void }) {
  const current = OPTIONS.find((o) => o.value === value.quantize);
  return (
    <div className="timing">
      <div className="chips" role="radiogroup" aria-label="Timing">
        {OPTIONS.map((o) => (
          <button key={o.value} type="button" role="radio" aria-checked={o.value === value.quantize}
            className={"chip" + (o.value === value.quantize ? " on" : "")} onClick={() => onChange({ ...value, quantize: o.value })}>
            {o.label}
          </button>
        ))}
      </div>
      <p className="muted">{current?.hint}</p>
    </div>
  );
}
