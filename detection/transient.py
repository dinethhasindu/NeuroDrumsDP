"""
NeuroDrums AI - Transient Shape Analysis.

Extracts per-event transient features:
  - Attack time (onset → peak)
  - Decay time (peak → 10% of peak)
  - Transient shape fingerprint
  - HPSS-based percussive/harmonic ratio
  - 46-dimensional feature vector for classification
"""
from __future__ import annotations
import numpy as np
import librosa
from typing import Dict, Any, Optional
from core.constants import N_FFT, HOP_LENGTH


DEFAULT_WINDOW = 0.200   # seconds of audio to analyze per event
PRE_PAD = 0.010          # seconds before onset to include


def extract_features(
    y: np.ndarray,
    sr: int,
    onset_time: float,
    window: float = DEFAULT_WINDOW,
    pre_pad: float = PRE_PAD,
    hop_length: int = HOP_LENGTH,
    n_fft: int = N_FFT,
) -> Dict[str, float]:
    """
    Extract a 46-dimensional feature dict for a single drum event.

    Returns a dict with all feature names as keys.
    """
    # Slice event audio
    a = max(0, int((onset_time - pre_pad) * sr))
    b = min(len(y), int((onset_time + window) * sr))
    x = y[a:b].astype(np.float32)

    if len(x) < 64:
        return _zero_features()

    feats: Dict[str, float] = {}

    # ── Time domain ───────────────────────────────────────────────
    rms = float(np.sqrt(np.mean(x ** 2)) + 1e-9)
    peak = float(np.max(np.abs(x)) + 1e-9)
    feats["rms"] = rms
    feats["peak"] = peak
    feats["crest_factor"] = peak / rms
    feats["duration"] = len(x) / sr

    # Zero crossing rate
    feats["zcr"] = float(librosa.feature.zero_crossing_rate(x, frame_length=min(512, len(x))).mean())

    # Attack time: samples from start to peak
    peak_idx = int(np.argmax(np.abs(x)))
    feats["attack_time"] = peak_idx / sr
    feats["attack_frac"] = peak_idx / max(1, len(x))

    # Decay time: samples from peak to 10% of peak
    tail = np.abs(x[peak_idx:])
    thresh = peak * 0.1
    decay_idx = np.argmax(tail < thresh) if np.any(tail < thresh) else len(tail)
    feats["decay_time"] = decay_idx / sr

    # ── Spectral features ───────────────────────────────────────────
    nfft = min(n_fft, 2 ** int(np.floor(np.log2(len(x)))))
    nfft = max(64, nfft)
    hop = min(hop_length, nfft // 2)
    S = np.abs(librosa.stft(x, n_fft=nfft, hop_length=hop))
    S_power = S ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=nfft)

    # Per-band energy ratios
    e_mean = S_power.mean(axis=1)
    total_e = e_mean.sum() + 1e-9

    low_mask = freqs < 200
    mid_mask = (freqs >= 200) & (freqs < 3000)
    high_mask = freqs >= 3000
    low_e  = e_mean[low_mask].sum()
    mid_e  = e_mean[mid_mask].sum()
    high_e = e_mean[high_mask].sum()

    feats["low_energy"]  = low_e / total_e
    feats["mid_energy"]  = mid_e / total_e
    feats["high_energy"] = high_e / total_e

    # Sub-bass (<80 Hz)
    feats["subbass_energy"] = e_mean[freqs < 80].sum() / total_e

    # Spectral centroid
    sc = librosa.feature.spectral_centroid(S=S, sr=sr)
    feats["spectral_centroid"]     = float(sc.mean())
    feats["spectral_centroid_std"] = float(sc.std())

    # Spectral bandwidth
    sb = librosa.feature.spectral_bandwidth(S=S, sr=sr)
    feats["spectral_bandwidth"] = float(sb.mean())

    # Spectral rolloff
    sr_feat = librosa.feature.spectral_rolloff(S=S, sr=sr, roll_percent=0.85)
    feats["spectral_rolloff"] = float(sr_feat.mean())

    # Spectral flatness (noisiness)
    sf_feat = librosa.feature.spectral_flatness(S=S)
    feats["spectral_flatness"] = float(sf_feat.mean())

    # Spectral flux (positive only)
    flux = np.maximum(0, np.diff(S, axis=1)).sum(axis=0)
    feats["spectral_flux"] = float(flux.mean()) if len(flux) > 0 else 0.0
    feats["spectral_flux_max"] = float(flux.max()) if len(flux) > 0 else 0.0

    # Onset strength shape
    env = librosa.onset.onset_strength(y=x, sr=sr, hop_length=hop)
    feats["onset_strength_peak"] = float(env.max()) if len(env) > 0 else 0.0
    feats["onset_strength_mean"] = float(env.mean()) if len(env) > 0 else 0.0
    feats["onset_concentration"] = (
        float(np.argmax(env)) / max(1, len(env) - 1) if len(env) > 1 else 0.0
    )

    # ── HPSS: harmonic vs percussive ratio ───────────────────────────
    try:
        D = librosa.stft(x, n_fft=nfft, hop_length=hop)
        H, P = librosa.decompose.hpss(D)
        h_energy = float(np.abs(H).mean())
        p_energy = float(np.abs(P).mean())
        total_hp = h_energy + p_energy + 1e-9
        feats["harmonic_ratio"]   = h_energy / total_hp
        feats["percussive_ratio"] = p_energy / total_hp
    except Exception:
        feats["harmonic_ratio"]   = 0.5
        feats["percussive_ratio"] = 0.5

    # ── MFCCs (first 13 coefficients, first frame) ──────────────────
    try:
        mfccs = librosa.feature.mfcc(y=x, sr=sr, n_mfcc=13, hop_length=hop)
        for i in range(13):
            feats[f"mfcc_{i}"] = float(mfccs[i].mean())
    except Exception:
        for i in range(13):
            feats[f"mfcc_{i}"] = 0.0

    # ── Velocity and dynamics ─────────────────────────────────
    feats["velocity"] = float(np.clip(rms * 10, 0, 1))

    return feats


def feature_vector(feats: Dict[str, float]) -> np.ndarray:
    """
    Convert feature dict to a fixed-order 1D float32 array
    suitable for ML classifiers.
    """
    ordered_keys = [
        "rms", "peak", "crest_factor", "duration",
        "zcr", "attack_time", "attack_frac", "decay_time",
        "low_energy", "mid_energy", "high_energy", "subbass_energy",
        "spectral_centroid", "spectral_centroid_std", "spectral_bandwidth",
        "spectral_rolloff", "spectral_flatness",
        "spectral_flux", "spectral_flux_max",
        "onset_strength_peak", "onset_strength_mean", "onset_concentration",
        "harmonic_ratio", "percussive_ratio", "velocity",
    ] + [f"mfcc_{i}" for i in range(13)]

    return np.array([feats.get(k, 0.0) for k in ordered_keys], dtype=np.float32)


def _zero_features() -> Dict[str, float]:
    """Return a zero-valued feature dict for invalid/empty events."""
    feats = {
        "rms": 0.0, "peak": 0.0, "crest_factor": 0.0, "duration": 0.0,
        "zcr": 0.0, "attack_time": 0.0, "attack_frac": 0.0, "decay_time": 0.0,
        "low_energy": 0.0, "mid_energy": 0.0, "high_energy": 0.0, "subbass_energy": 0.0,
        "spectral_centroid": 0.0, "spectral_centroid_std": 0.0, "spectral_bandwidth": 0.0,
        "spectral_rolloff": 0.0, "spectral_flatness": 0.0,
        "spectral_flux": 0.0, "spectral_flux_max": 0.0,
        "onset_strength_peak": 0.0, "onset_strength_mean": 0.0, "onset_concentration": 0.0,
        "harmonic_ratio": 0.0, "percussive_ratio": 0.0, "velocity": 0.0,
    }
    for i in range(13):
        feats[f"mfcc_{i}"] = 0.0
    return feats
