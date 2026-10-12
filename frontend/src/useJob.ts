import { useEffect, useState } from "react";
import type { JobState } from "./api";

/** Follows a job's progress over server-sent events. */
export function useJob(id: string | null): JobState | null {
  const [state, setState] = useState<JobState | null>(null);
  useEffect(() => {
    setState(null);
    if (!id) return;
    const es = new EventSource(`/jobs/${id}/events`);
    es.onmessage = (e) => setState(JSON.parse(e.data));
    return () => es.close();
  }, [id]);
  return state;
}
