"""
NeuroDrums AI - Replacement Pitch Module.

Applies pitch shifting and time stretching to replacement samples.
"""
from __future__ import annotations
import numpy as np

def apply_pitch_and_speed(
    audio: np.ndarray,
    sr: int,
    pitch_semitones: float = 0.0,
    speed: float = 1.0,
) -> np.ndarray:
    """
    Apply pitch shifting (semitones) and time stretching.
    """
    if pitch_semitones == 0.0 and speed == 1.0:
        return audio

    try:
        import librosa
        out = audio

        # librosa's pitch shift maintains duration
        if pitch_semitones != 0.0:
            out = librosa.effects.pitch_shift(out, sr=sr, n_steps=pitch_semitones)

        # librosa's time stretch changes duration
        if speed != 1.0:
            out = librosa.effects.time_stretch(out, rate=speed)

        return out.astype(np.float32)
    except Exception:
        # Fallback if librosa fails or is slow (e.g. simple resampling for pitch+speed linked)
        # If we just resample, it changes pitch AND speed simultaneously.
        print("[Pitch] librosa time/pitch shift failed, returning original audio")
        return audio
