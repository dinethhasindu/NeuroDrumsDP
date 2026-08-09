"""
NeuroDrums AI - Replacement Masking Module.

Attenuates the original audio at the location of a replaced event.
"""
from __future__ import annotations
import numpy as np

def apply_mask(
    original_audio: np.ndarray,
    start_sample: int,
    end_sample: int,
    attenuation: float = 1.0,  # 0.0 = no attenuation, 1.0 = total silence
    fade_samples: int = 441,   # ~10ms fade in/out to prevent clicks
) -> np.ndarray:
    """
    Apply a volume mask (ducking) to a region of the original audio.
    Operates in-place on a copy or the original array.
    """
    if attenuation <= 0.0:
        return original_audio

    n = len(original_audio)
    start_sample = max(0, min(start_sample, n))
    end_sample = max(0, min(end_sample, n))
    length = end_sample - start_sample

    if length <= 0:
        return original_audio

    # Create ducking curve
    gain = 1.0 - np.clip(attenuation, 0.0, 1.0)
    curve = np.full(length, gain, dtype=np.float32)

    # Fade out at the start of the mask (so original audio fades down)
    fade_in_len = min(fade_samples, length // 2)
    if fade_in_len > 0:
        fade_down = np.linspace(1.0, gain, fade_in_len, dtype=np.float32)
        curve[:fade_in_len] = fade_down

    # Fade in at the end of the mask (so original audio fades back up)
    fade_out_len = min(fade_samples, length - fade_in_len)
    if fade_out_len > 0:
        fade_up = np.linspace(gain, 1.0, fade_out_len, dtype=np.float32)
        curve[-fade_out_len:] = fade_up

    masked = original_audio.copy()
    masked[start_sample:end_sample] *= curve

    return masked
