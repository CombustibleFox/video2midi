import type { NoteOut } from "./api";

/** Minimal Web Audio piano-ish synth: two partials with a decaying envelope. */
export class Player {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private startedAt = 0; // ctx time corresponding to song time `offset`
  private offset = 0;
  private rate = 1;
  playing = false;
  private stopTimer: number | undefined;

  constructor(private notes: NoteOut[], private duration: number) {}

  get position(): number {
    if (!this.playing || !this.ctx) return this.offset;
    return Math.min(this.duration, this.offset + (this.ctx.currentTime - this.startedAt) * this.rate);
  }

  async play(from: number, hands: { R: boolean; L: boolean }, rate = 1) {
    this.stop(from);
    this.ctx ??= new AudioContext();
    await this.ctx.resume();
    const ctx = this.ctx;
    const master = ctx.createGain();
    master.gain.value = 0.25;
    master.connect(ctx.destination);
    this.master = master;
    this.rate = rate;
    const t0 = ctx.currentTime + 0.05;
    for (const n of this.notes) {
      if (!hands[n.hand] || n.end <= from) continue;
      const start = t0 + Math.max(0, n.start - from) / rate;
      const end = t0 + (n.end - from) / rate;
      const f = 440 * Math.pow(2, (n.pitch - 69) / 12);
      const g = ctx.createGain();
      const peak = 0.5 * Math.min(1, 1.6 - n.pitch / 90);
      g.gain.setValueAtTime(0, start);
      g.gain.linearRampToValueAtTime(peak, start + 0.008);
      g.gain.exponentialRampToValueAtTime(peak * 0.25, start + 0.4);
      g.gain.setValueAtTime(peak * 0.25, Math.max(start + 0.4, end));
      g.gain.linearRampToValueAtTime(0.0001, Math.max(start + 0.45, end + 0.15));
      g.connect(master);
      for (const [type, mult, vol] of [["triangle", 1, 1], ["sine", 2, 0.3]] as const) {
        const o = ctx.createOscillator();
        const og = ctx.createGain();
        og.gain.value = vol;
        o.type = type;
        o.frequency.value = f * mult;
        o.connect(og).connect(g);
        o.start(start);
        o.stop(Math.max(start + 0.5, end + 0.2));
      }
    }
    this.offset = from;
    this.startedAt = t0;
    this.playing = true;
    window.clearTimeout(this.stopTimer);
    this.stopTimer = window.setTimeout(() => this.stop(this.duration), ((this.duration - from) / rate + 0.5) * 1000);
  }

  stop(position = 0) {
    window.clearTimeout(this.stopTimer);
    if (this.master) {
      this.master.disconnect(); // silences everything already scheduled
      this.master = null;
    }
    this.playing = false;
    this.offset = position;
  }

  pause() {
    this.stop(this.position);
  }
}
