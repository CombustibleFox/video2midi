import { useCallback, useLayoutEffect, useState } from "react";

export type ThemeId = "midnight" | "daylight" | "paper" | "neon" | "roadtrip" | "seaside" | "fox";

export interface ThemeInfo {
  id: ThemeId;
  label: string;
  blurb: string;
  /** background, surface, accent, right hand, left hand - for the little preview chip */
  swatch: [string, string, string, string, string];
  playful?: "car" | "fish" | "fox";
}

export const THEMES: ThemeInfo[] = [
  { id: "midnight", label: "Midnight", blurb: "Calm and dark", swatch: ["#14171d", "#1c212b", "#4c8dff", "#4cc38a", "#5b9dff"] },
  { id: "daylight", label: "Daylight", blurb: "Clean and bright", swatch: ["#f3f5f9", "#ffffff", "#2f6bff", "#16a36a", "#2f6bff"] },
  { id: "paper", label: "Sheet Music", blurb: "Warm paper and ink", swatch: ["#f4ecd8", "#fbf6e8", "#8b2e2e", "#2f7a4f", "#2b4c7e"] },
  { id: "neon", label: "Neon Keys", blurb: "Glowing falling notes", swatch: ["#07060d", "#120f1f", "#ff3ea5", "#39ffb0", "#38b6ff"] },
  { id: "roadtrip", label: "Road Trip", blurb: "Sunny roads and a little purple car", swatch: ["#8fd8ff", "#ffffff", "#7a3fc0", "#3fbf3f", "#2f7bff"], playful: "car" },
  { id: "seaside", label: "Seaside Adventure", blurb: "Bubbles and a friendly fish", swatch: ["#0a7aa8", "#e9fbff", "#ff8f1f", "#ffd23f", "#6fe3ff"], playful: "fish" },
  { id: "fox", label: "Fox Den", blurb: "Autumn woods and a curious fox", swatch: ["#ffb26b", "#fff4e0", "#e8590c", "#ff9f43", "#5cc2a6"], playful: "fox" },
];

const KEY = "v2m-theme";

function initial(): ThemeId {
  try {
    const saved = localStorage.getItem(KEY) as ThemeId | null;
    if (saved && THEMES.some((t) => t.id === saved)) return saved;
  } catch {
    /* storage can be unavailable */
  }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "daylight" : "midnight";
}

/** The selected theme, remembered between visits and applied to the page as data-theme. */
export function useTheme(): [ThemeInfo, (id: ThemeId) => void] {
  const [id, setId] = useState<ThemeId>(initial);
  // layout effect: the colours must be in place before child components (the piano roll) read them
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = id;
    document.documentElement.dataset.playful = THEMES.find((t) => t.id === id)?.playful ? "yes" : "no";
    try {
      localStorage.setItem(KEY, id);
    } catch {
      /* ignore */
    }
  }, [id]);
  const set = useCallback((next: ThemeId) => setId(next), []);
  return [THEMES.find((t) => t.id === id)!, set];
}

/** Read a CSS variable of the active theme, e.g. for drawing on a canvas. */
export const themeColor = (name: string, fallback: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
