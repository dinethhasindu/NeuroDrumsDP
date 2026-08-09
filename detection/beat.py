"""
NeuroDrums AI - BPM Detection & Beat Grid.

Provides:
  - Automatic BPM estimation using librosa
  - Manual BPM override
  - Beat grid generation for snap-to-grid
  - Time-to-grid-position mapping
"""
from __future__ import annotations
import numpy as np
import librosa
from typing import Optional, List
from core.constants import HOP_LENGTH


GRID_DIVISIONS = ["1/4", "1/8", "1/16", "1/32", "1/64",
                  "1/4T", "1/8T", "1/16T"]  # T = triplet


def detect_bpm(
    y: np.ndarray,
    sr: int,
    hop_length: int = HOP_LENGTH,
) -> float:
    """
    Estimate BPM using librosa beat tracker.
    Falls back to 120 BPM if estimation fails.

    Returns:
        Estimated tempo in BPM (float)
    """
    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length, units="time")
        if hasattr(tempo, '__len__'):
            tempo = float(tempo[0])
        else:
            tempo = float(tempo)
        # Sanity check: drum stems rarely < 50 or > 300 BPM
        if 50.0 <= tempo <= 300.0:
            return round(tempo, 1)
        # Try octave correction
        if tempo < 50:
            return round(tempo * 2, 1)
        if tempo > 300:
            return round(tempo / 2, 1)
        return 120.0
    except Exception:
        return 120.0


def build_grid(
    bpm: float,
    duration: float,
    division: str = "1/16",
    time_sig_num: int = 4,
    time_sig_den: int = 4,
) -> np.ndarray:
    """
    Build a regular beat grid array of time positions.

    Args:
        bpm:          tempo in BPM
        duration:     total audio duration in seconds
        division:     grid subdivision ('1/4', '1/8', '1/16', '1/32', '1/64',
                                         '1/4T', '1/8T', '1/16T')
        time_sig_num: beats per bar
        time_sig_den: beat value (4 = quarter note)

    Returns:
        Array of grid time positions in seconds
    """
    beat_duration = 60.0 / bpm  # duration of one quarter note

    # Map division to multiplier relative to one quarter note
    division_map = {
        "1/4":   1.0,
        "1/8":   0.5,
        "1/16":  0.25,
        "1/32":  0.125,
        "1/64":  0.0625,
        "1/4T":  2.0 / 3.0,
        "1/8T":  1.0 / 3.0,
        "1/16T": 1.0 / 6.0,
    }
    mult = division_map.get(division, 0.25)
    step = beat_duration * mult

    if step <= 0:
        return np.array([])

    return np.arange(0.0, duration, step, dtype=np.float64)


def snap_to_grid(
    time: float,
    grid: np.ndarray,
    max_snap_ms: float = 50.0,
) -> float:
    """
    Snap a time position to the nearest grid point.

    Args:
        time:         time in seconds
        grid:         array of grid positions
        max_snap_ms:  maximum snapping distance in milliseconds

    Returns:
        Snapped time, or original time if no grid point is close enough
    """
    if len(grid) == 0:
        return time
    diffs = np.abs(grid - time)
    idx = int(np.argmin(diffs))
    if diffs[idx] <= max_snap_ms / 1000.0:
        return float(grid[idx])
    return time


def time_to_beats(time: float, bpm: float) -> float:
    """Convert time in seconds to beat count."""
    return time * bpm / 60.0


def beats_to_time(beats: float, bpm: float) -> float:
    """Convert beat count to time in seconds."""
    return beats * 60.0 / bpm
