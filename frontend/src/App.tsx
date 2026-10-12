import { useEffect, useState } from "react";
import { Calibration, deleteJob, DEFAULT_SETTINGS, processJob, Settings } from "./api";
import CalibrationView from "./CalibrationView";
import Mascot from "./Mascot";
import Progress from "./Progress";
import ResultView from "./ResultView";
import Scene from "./Scene";
import StartForm from "./StartForm";
import Stepper from "./Stepper";
import ThemeSwitcher from "./ThemeSwitcher";
import { useStored } from "./storage";
import { useTheme } from "./themes";
import { useJob } from "./useJob";

type Step = "start" | "calibrate" | "result";
const WORKING = ["queued", "downloading", "calibrating", "extracting", "exporting"];

export default function App() {
  const [theme, setTheme] = useTheme();
  const [jobId, setJobId] = useState<string | null>(null);
  const [settings, setSettings] = useStored<Settings>("v2m-settings", DEFAULT_SETTINGS);
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
      setStep("start"); // hide the form while the server works; status events bring us back
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const working = !!jobId && !!job && WORKING.includes(job.status);
  const failed = job?.status === "error";
  const stepNo = !jobId ? 1 : step === "result" && job?.status === "done" ? 3 : step === "calibrate" || (working && job!.status === "extracting") || job?.status === "exporting" ? 2 : 1;

  return (
    <>
      <Scene theme={theme.id} />
      <main>
        <header className="top">
          <div className="brand">
            {theme.playful ? <Mascot kind={theme.playful} size={38} /> : <span className="logo" aria-hidden="true">🎹</span>}
            <div>
              <h1>video2midi</h1>
              <p className="muted">Piano video in, two-hand MIDI out</p>
            </div>
          </div>
          <ThemeSwitcher theme={theme} onChange={setTheme} />
        </header>

        <Stepper step={stepNo as 1 | 2 | 3} busy={working} />

        {error && <p className="notice err" role="alert">{error}</p>}
        {failed && (
          <div className="card">
            <h2>That didn't work</h2>
            <p className="notice err" role="alert">{job!.error}</p>
            <p className="muted">If this was a YouTube link, the site may be blocking the download. Saving the video and dropping the file in works every time.</p>
            <div className="row">
              {job!.message === "Failed" && step === "calibrate" && <button onClick={() => setStep("calibrate")}>Back to detection</button>}
              <button className="primary" onClick={reset}>Try again</button>
            </div>
          </div>
        )}

        {!jobId && <StartForm settings={settings} onSettings={setSettings} onStarted={setJobId} />}
        {working && <Progress job={job} theme={theme} />}
        {jobId && !working && !failed && step === "calibrate" && (
          <CalibrationView jobId={jobId} initialSettings={settings} onConfirm={confirm} onBack={reset} />
        )}
        {jobId && !working && step === "result" && job?.status === "done" && (
          <ResultView jobId={jobId} themeId={theme.id} onAdjust={() => setStep("calibrate")} onReset={reset} />
        )}

        <footer>Everything runs on your computer. Videos are not uploaded anywhere.</footer>
      </main>
    </>
  );
}
