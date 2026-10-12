import { useEffect, useState } from "react";
import { Calibration, deleteJob, DEFAULT_SETTINGS, processJob, Settings } from "./api";
import CalibrationView from "./CalibrationView";
import Progress from "./Progress";
import ResultView from "./ResultView";
import StartForm from "./StartForm";
import { useJob } from "./useJob";

type Step = "start" | "calibrate" | "result";

export default function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [step, setStep] = useState<Step>("start");
  const [error, setError] = useState<string | null>(null);
  const job = useJob(jobId);

  // follow the server-side job state through the steps
  useEffect(() => {
    if (!job) return;
    if (job.status === "awaiting_confirmation") setStep("calibrate");
    else if (job.status === "done") setStep("result");
  }, [job?.status, job?.version]);

  const reset = () => {
    if (jobId) deleteJob(jobId);
    setJobId(null);
    setStep("start");
    setError(null);
  };

  const confirm = async (cal: Calibration, s: Settings) => {
    setError(null);
    setSettings(s);
    try {
      await processJob(jobId!, cal, s);
      setStep("start"); // hide forms while the server works; status events bring us back
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const working = jobId && job && ["queued", "downloading", "calibrating", "extracting", "exporting"].includes(job.status);

  return (
    <main>
      <header>
        <h1>video2midi</h1>
        <p className="muted">Turn a Synthesia-style piano video into a MIDI file with separate left and right hand tracks.</p>
      </header>
      {error && <p className="error">{error}</p>}
      {job?.status === "error" && (
        <div className="card">
          <p className="error">{job.error}</p>
          <div className="row">
            {step === "calibrate" || job.message === "Failed" ? <button onClick={() => setStep("calibrate")}>Back to detection</button> : null}
            <button onClick={reset}>Start over</button>
          </div>
        </div>
      )}
      {!jobId && <StartForm onStarted={(id, s) => { setJobId(id); setSettings(s); }} />}
      {working && <Progress job={job} />}
      {jobId && !working && step === "calibrate" && job?.status !== "error" && (
        <CalibrationView jobId={jobId} initialSettings={settings} onConfirm={confirm} />
      )}
      {jobId && !working && step === "result" && job?.status === "done" && (
        <ResultView jobId={jobId} onAdjust={() => setStep("calibrate")} onReset={reset} />
      )}
    </main>
  );
}
