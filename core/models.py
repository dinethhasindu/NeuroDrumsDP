"""
NeuroDrums AI - Core data models.
All primary data structures used throughout the application.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import uuid


@dataclass
class DrumEvent:
    """A single detected drum event with all associated metadata."""
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "Kick"           # Lane type (from LANE_NAMES)
    subtype: str = ""            # More specific sub-classification

    # Timing
    start: float = 0.0           # seconds from track start
    end: float = 0.0             # seconds; computed from onset + decay
    duration: float = 0.0        # seconds

    # Dynamics
    velocity: float = 0.8        # 0.0–1.0 (original detected amplitude)
    confidence: float = 0.5      # 0.0–1.0 (classifier confidence)

    # State flags
    muted: bool = False
    removed: bool = False
    selected: bool = False
    uncertain: bool = False      # Low confidence flag

    # Replacement parameters
    volume_db: float = 0.0       # dB offset applied to replacement
    pitch: float = 0.0           # semitones
    punch: float = 0.65          # 0–1 (transient emphasis)
    decay_ms: float = 450.0      # milliseconds
    speed: float = 1.0           # 0.5–2.0
    fade_in_ms: float = 2.0      # milliseconds
    fade_out_ms: float = 10.0    # milliseconds
    pan: float = 0.0             # -1 (L) to +1 (R)
    timing_offset_ms: float = 0.0  # manual timing nudge

    # Replacement mode
    replace_mode: str = "replace"   # "replace" / "layer" / "original"
    original_attenuation: float = 1.0  # 0–1 (how much to remove original)
    match_velocity: bool = True
    velocity_curve: str = "linear"  # "soft" / "linear" / "hard"

    # Sample reference
    replacement_sample: Optional[str] = None  # path to WAV file

    # Analysis metadata (read-only, set by detector)
    spectral_centroid: float = 0.0
    low_energy: float = 0.0
    mid_energy: float = 0.0
    high_energy: float = 0.0
    zcr: float = 0.0
    attack_time: float = 0.0
    onset_strength: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "id": self.id,
            "type": self.type,
            "subtype": self.subtype,
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "velocity": self.velocity,
            "confidence": self.confidence,
            "muted": self.muted,
            "removed": self.removed,
            "uncertain": self.uncertain,
            "volume_db": self.volume_db,
            "pitch": self.pitch,
            "punch": self.punch,
            "decay_ms": self.decay_ms,
            "speed": self.speed,
            "fade_in_ms": self.fade_in_ms,
            "fade_out_ms": self.fade_out_ms,
            "pan": self.pan,
            "timing_offset_ms": self.timing_offset_ms,
            "replace_mode": self.replace_mode,
            "original_attenuation": self.original_attenuation,
            "match_velocity": self.match_velocity,
            "velocity_curve": self.velocity_curve,
            "replacement_sample": self.replacement_sample,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DrumEvent":
        """Deserialize from dict."""
        e = cls()
        for k, v in d.items():
            if hasattr(e, k):
                setattr(e, k, v)
        return e

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.75:
            return "High"
        elif self.confidence >= 0.50:
            return "Medium"
        else:
            return "Low"

    @property
    def confidence_color(self) -> str:
        if self.confidence >= 0.75:
            return "#2dc653"
        elif self.confidence >= 0.50:
            return "#ffbe0b"
        else:
            return "#ff4d6d"


@dataclass
class LaneState:
    """Per-lane state managed by the main session."""
    name: str
    muted: bool = False
    soloed: bool = False
    volume: float = 1.0          # linear gain
    replacement_sample: Optional[str] = None
    color: str = "#888888"

    # Per-lane defaults (applied to new events in this lane)
    default_volume_db: float = 0.0
    default_pitch: float = 0.0
    default_punch: float = 0.65
    default_decay_ms: float = 450.0
    default_speed: float = 1.0
    default_fade_in_ms: float = 2.0
    default_fade_out_ms: float = 10.0
    default_replace_mode: str = "replace"
    default_attenuation: float = 1.0


@dataclass
class AudioInfo:
    """Metadata about a loaded audio file."""
    path: str = ""
    filename: str = ""
    duration: float = 0.0
    sample_rate: int = 44100
    channels: int = 1
    bit_depth: int = 16
    format: str = "WAV"


@dataclass
class ProjectState:
    """Complete project state, used for save/load."""
    version: str = "1.0"
    source_path: str = ""
    drum_stem_path: str = ""       # Path after Demucs separation
    bpm: float = 120.0
    time_signature_num: int = 4
    time_signature_den: int = 4
    events: List[DrumEvent] = field(default_factory=list)
    lane_states: Dict[str, LaneState] = field(default_factory=dict)
    zoom: float = 1.0
    scroll_offset: float = 0.0
    playhead: float = 0.0
    audio_info: Optional[AudioInfo] = None
