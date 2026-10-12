from dataclasses import dataclass, asdict


@dataclass
class Note:
    pitch: int
    start: float  # seconds
    end: float  # seconds
    hand: str = "R"  # "R" or "L"

    def to_dict(self) -> dict:
        return asdict(self)
