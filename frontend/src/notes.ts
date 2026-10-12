const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
export const noteName = (m: number) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;
export const isBlack = (m: number) => [1, 3, 6, 8, 10].includes(m % 12);

const BLACK_AFTER = [1, 1, 0, 1, 1, 1, 0];
const WHITE_SEMIS = [0, 2, 4, 5, 7, 9, 11];

/** Pitch of the rightmost key of a keyboard with `whiteKeys` white keys starting at MIDI pitch `first`. */
export function lastMidi(first: number, whiteKeys: number): number {
  let idx = WHITE_SEMIS.indexOf(first % 12);
  if (idx < 0) idx = 0;
  let pitch = first;
  for (let i = 0; i < whiteKeys - 1; i++) pitch += BLACK_AFTER[(idx + i) % 7] ? 2 : 1;
  return pitch;
}

export const fmtTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, "0")}`;
