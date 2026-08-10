from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import uuid

@dataclass
class AudioInfo:
    path: str = ''
    filename: str = ''
    duration: float = 0.0
    sample_rate: int = 44100
    channels: int = 1
    bit_depth: int = 16
    format: str = 'WAV'

@dataclass
class DrumEvent:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: str = 'Kick'
    subtype: str = ''
    start: float = 0.0
    end: float = 0.08
    duration: float = 0.08
    velocity: float = 0.8
    confidence: float = 0.5
    muted: bool = False
    removed: bool = False
    uncertain: bool = False
    volume_db: float = 0.0
    pitch: float = 0.0
    punch: float = 0.65
    decay_ms: float = 450.0
    speed: float = 1.0
    fade_in_ms: float = 2.0
    fade_out_ms: float = 10.0
    pan: float = 0.0
    timing_offset_ms: float = 0.0
    replacement_sample: Optional[str] = None
    spectral_centroid: float = 0.0
    low_energy: float = 0.0
    mid_energy: float = 0.0
    high_energy: float = 0.0
    zcr: float = 0.0
    onset_strength: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DrumEvent':
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

@dataclass
class LaneState:
    name: str
    muted: bool = False
    soloed: bool = False
    volume: float = 1.0
    pan: float = 0.0
    replacement_sample: Optional[str] = None
    color: str = '#888888'

@dataclass
class ProjectState:
    version: str = APP_VERSION if False else '1.1'
    source_path: str = ''
    drum_stem_path: str = ''
    bpm: float = 120.0
    events: List[DrumEvent] = field(default_factory=list)
    lane_states: Dict[str, LaneState] = field(default_factory=dict)
    zoom: float = 120.0
    playhead: float = 0.0
    audio_info: Optional[AudioInfo] = None

    def to_dict(self):
        return {
            'project': 'NeuroDrumsDP', 'version': self.version, 'source_path': self.source_path,
            'drum_stem_path': self.drum_stem_path, 'bpm': self.bpm,
            'events': [e.to_dict() for e in self.events],
            'lanes': {k: asdict(v) for k, v in self.lane_states.items()},
            'zoom': self.zoom, 'playhead': self.playhead,
            'audio_info': asdict(self.audio_info) if self.audio_info else None,
        }
