"""
NeuroDrums AI - Advanced Onset Detection.

Uses dual-method detection:
  1. librosa SuperFlux onset envelope
  2. Custom high-frequency content (HFC) spectral flux

Consensus peaks from both methods yield accurate onset times
with configurable sensitivity presets.
"""
from __future__ import annotations
import numpy as np
import librosa
from typing import List, Tuple, Optional
from core.constants import HOP_LENGTH, N_FFT, SENSITIVITY_PRESETS


def detect_onsets(
    y: np.ndarray,
    sr: int,
    sensitivity: str = "medium",
    min_separation_ms: float = 30.0,
    hop_length: int = HOP_LENGTH,
    n_fft: int = N_FFT,
    progress_cb=None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect drum onset times in an audio signal.

    Args:
        y:                 mono float32 audio
        sr:                sample rate
        sensitivity:       'low' | 'medium' | 'high'
        min_separation_ms: minimum gap between onsets in milliseconds
        hop_length:        STFT hop length
        n_fft:             FFT window size
        progress_cb:       optional callback(float 0..1)

    Returns:
        (onset_times, onset_strengths) - parallel arrays of float32
    """
    params = SENSITIVITY_PRESETS.get(sensitivity, SENSITIVITY_PRESETS["medium"])
    min_sep_frames = max(1, int(min_separation_ms / 1000.0 * sr / hop_length))

    if progress_cb:
        progress_cb(0.1)

    # ─────────────────────────────────────────────────────────
    # Method 1: librosa default onset envelope (SuperFlux-inspired)
    # ─────────────────────────────────────────────────────────
    env1 = librosa.onset.onset_strength(
        y=y, sr=sr, hop_length=hop_length, n_fft=n_fft,
        aggregate=np.median,
    )
    frames1 = librosa.onset.onset_detect(
        onset_envelope=env1, sr=sr, hop_length=hop_length,
        backtrack=True,
        pre_max=params["pre_max"],
        post_max=params["post_max"],
        pre_avg=params["pre_avg"],
        post_avg=params["post_avg"],
        delta=params["delta"],
        wait=min_sep_frames,
    )

    if progress_cb:
        progress_cb(0.4)

    # ─────────────────────────────────────────────────────────
    # Method 2: High-Frequency Content (HFC) spectral flux
    # Better sensitivity to percussive transients
    # ─────────────────────────────────────────────────────────
    env2 = _hfc_onset_envelope(y, sr, hop_length, n_fft)
    frames2 = librosa.onset.onset_detect(
        onset_envelope=env2, sr=sr, hop_length=hop_length,
        backtrack=True,
        pre_max=params["pre_max"],
        post_max=params["post_max"],
        pre_avg=params["pre_avg"],
        post_avg=params["post_avg"],
        delta=params["delta"] * 0.85,
        wait=min_sep_frames,
    )

    if progress_cb:
        progress_cb(0.7)

    # ─────────────────────────────────────────────────────────
    # Merge: union of both frame sets, deduplicate with min_separation
    # ─────────────────────────────────────────────────────────
    all_frames = np.unique(np.concatenate([frames1, frames2]))
    merged = _deduplicate_frames(all_frames, env1, min_sep_frames)

    times = librosa.frames_to_time(merged, sr=sr, hop_length=hop_length).astype(np.float32)

    # Build combined strength envelope at merged frame positions
    env_combined = (env1 + env2) / 2.0
    strengths = np.array(
        [float(env_combined[f]) if f < len(env_combined) else 0.0 for f in merged],
        dtype=np.float32,
    )
    # Normalize strengths
    if strengths.max() > 0:
        strengths = strengths / strengths.max()

    if progress_cb:
        progress_cb(1.0)

    return times, strengths


def _hfc_onset_envelope(y: np.ndarray, sr: int, hop_length: int, n_fft: int) -> np.ndarray:
    """
    High-Frequency Content onset envelope.
    Weights higher frequencies more, making it sensitive to
    fast transients characteristic of kick/snare attacks.
    """
    D = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    # HFC weights: linearly increasing from 0 to 1 across frequency bins
    weights = np.linspace(0.1, 1.0, D.shape[0])[:, np.newaxis]
    weighted = D * weights
    # Spectral flux: positive differences only
    flux = np.maximum(0, np.diff(weighted, axis=1))
    env = flux.sum(axis=0)
    # Prepend a zero to match original frame count
    env = np.concatenate([[0.0], env])
    # Smooth slightly
    from scipy.signal import savgol_filter
    if len(env) > 11:
        env = savgol_filter(env, window_length=7, polyorder=2)
    env = np.maximum(0, env).astype(np.float32)
    # Normalize
    if env.max() > 0:
        env = env / env.max()
    return env


def _deduplicate_frames(
    frames: np.ndarray,
    envelope: np.ndarray,
    min_sep: int,
) -> np.ndarray:
    """
    Remove frames closer than min_sep to each other,
    keeping the one with the highest envelope value.
    """
    if len(frames) == 0:
        return frames
    kept = []
    i = 0
    while i < len(frames):
        j = i + 1
        cluster = [frames[i]]
        while j < len(frames) and frames[j] - frames[i] < min_sep:
            cluster.append(frames[j])
            j += 1
        # keep the frame with highest envelope strength
        best = max(cluster, key=lambda f: envelope[f] if f < len(envelope) else 0.0)
        kept.append(best)
        i = j
    return np.array(kept, dtype=int)
