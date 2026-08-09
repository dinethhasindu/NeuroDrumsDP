"""
NeuroDrums AI - Replacement Alignment Module.

Aligns replacement samples to original transients to prevent phase cancellation
and ensure rhythmic accuracy.
"""
from __future__ import annotations
import numpy as np

def align_transient(
    original_audio: np.ndarray,
    replacement_audio: np.ndarray,
    max_shift_samples: int = 441,  # ~10ms at 44.1kHz
) -> np.ndarray:
    """
    Align replacement audio to the original audio using cross-correlation.
    """
    if len(original_audio) == 0 or len(replacement_audio) == 0:
        return replacement_audio

    # Use a small window for correlation (e.g. first 20ms)
    window_len = min(len(original_audio), len(replacement_audio), max_shift_samples * 2)
    if window_len < 10:
        return replacement_audio

    orig_win = original_audio[:window_len]
    repl_win = replacement_audio[:window_len]

    # Cross-correlate
    corr = np.correlate(orig_win, repl_win, mode='full')
    
    # The center of the correlation array corresponds to 0 shift
    center = len(repl_win) - 1
    
    # Restrict search to max_shift_samples
    start_idx = max(0, center - max_shift_samples)
    end_idx = min(len(corr), center + max_shift_samples + 1)
    
    if start_idx >= end_idx:
        return replacement_audio

    best_idx = start_idx + np.argmax(corr[start_idx:end_idx])
    shift = best_idx - center

    if shift == 0:
        return replacement_audio
    
    aligned = np.zeros_like(replacement_audio)
    if shift > 0:
        # Replacement needs to move right (delayed)
        aligned[shift:] = replacement_audio[:-shift]
    else:
        # Replacement needs to move left (advanced)
        shift = -shift
        aligned[:-shift] = replacement_audio[shift:]

    return aligned
