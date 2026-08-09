"""
NeuroDrums AI - Replacement Envelope Module.

Applies amplitude envelopes (fade in, fade out, decay, punch) to replacement samples.
"""
from __future__ import annotations
import numpy as np

def apply_envelope(
    audio: np.ndarray,
    sr: int,
    decay_ms: float = 450.0,
    fade_in_ms: float = 2.0,
    fade_out_ms: float = 10.0,
    punch: float = 0.65,
) -> np.ndarray:
    """
    Apply ADSR-like envelope and transient punch.
    """
    n = len(audio)
    if n == 0:
        return audio

    out = audio.copy()

    # 1. Decay length truncation
    decay_samples = int((decay_ms / 1000.0) * sr)
    if decay_samples > 0 and decay_samples < n:
        out = out[:decay_samples]
        n = len(out)

    envelope = np.ones(n, dtype=np.float32)

    # 2. Fade In
    fade_in_samples = int((fade_in_ms / 1000.0) * sr)
    fade_in_samples = min(fade_in_samples, n // 2)
    if fade_in_samples > 0:
        envelope[:fade_in_samples] = np.linspace(0.0, 1.0, fade_in_samples)

    # 3. Fade Out
    fade_out_samples = int((fade_out_ms / 1000.0) * sr)
    fade_out_samples = min(fade_out_samples, n - fade_in_samples)
    if fade_out_samples > 0:
        envelope[-fade_out_samples:] = np.linspace(1.0, 0.0, fade_out_samples)

    # 4. Punch (Transient emphasis)
    # Punch > 0.5 emphasizes the start, Punch < 0.5 softens it
    # Normal is 0.5. We map 0.0-1.0 to a curve.
    if punch != 0.5:
        punch_samples = min(int(0.05 * sr), n) # 50ms transient region
        if punch_samples > 0:
            # Map punch 0.0-1.0 to -12dB to +12dB (0.25x to 4.0x)
            if punch > 0.5:
                # 0.5->1.0 maps to 1.0->4.0
                peak_gain = 1.0 + (punch - 0.5) * 2.0 * 3.0
            else:
                # 0.0->0.5 maps to 0.25->1.0
                peak_gain = 0.25 + (punch * 1.5)
            
            punch_curve = np.linspace(peak_gain, 1.0, punch_samples)
            envelope[:punch_samples] *= punch_curve

    out *= envelope
    return out
