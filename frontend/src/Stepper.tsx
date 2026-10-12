const STEPS = ["Choose video", "Check detection", "Result"];

export default function Stepper({ step, busy }: { step: 1 | 2 | 3; busy: boolean }) {
  return (
    <ol className="stepper" aria-label="Progress">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const state = n < step ? "done" : n === step ? (busy ? "busy" : "now") : "todo";
        return (
          <li key={label} className={state} aria-current={n === step ? "step" : undefined}>
            <span className="dot">{state === "done" ? "✓" : n}</span>
            <span className="lbl">{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
