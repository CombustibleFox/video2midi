from dataclasses import dataclass, fields

# note value -> grid step in beats (quarter note = 1 beat)
GRIDS = {"1/4": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125}


@dataclass
class Settings:
    quantize: str = "1/16"  # key of GRIDS, or "off"
    tempo_override: float | None = None  # BPM
    split_pitch: int = 60  # fallback hand split: >= split is right hand
    min_note_s: float = 0.05
    gap_fill_frames: int = 1  # bridge detection dropouts up to this many frames
    velocity: int = 80
    start_s: float = 0.0
    end_s: float | None = None
    hit_offset: int = 4  # pixels above the keyboard where note colors are learned
    trim_to_first_note: bool = True

    @classmethod
    def from_dict(cls, d: dict | None) -> "Settings":
        names = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in (d or {}).items() if k in names})
        if s.quantize != "off" and s.quantize not in GRIDS:
            raise ValueError(f"quantize must be 'off' or one of {sorted(GRIDS)}")
        if not 1 <= s.velocity <= 127:
            raise ValueError("velocity must be 1-127")
        return s
