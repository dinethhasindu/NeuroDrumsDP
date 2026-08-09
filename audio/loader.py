"""
NeuroDrums AI - Audio Loader.

Supports: WAV, MP3, FLAC, AIFF, M4A, OGG via soundfile + librosa fallback.
Returns float32 mono audio at original sample rate.
Fills AudioInfo with file metadata.
"""
from __future__ import annotations
import os
import numpy as np
from typing import Tuple, Optional

from core.models import AudioInfo


def load_audio(
    path: str,
    target_sr: Optional[int] = None,
    mono: bool = True,
) -> Tuple[np.ndarray, int, AudioInfo]:
    """
    Load an audio file and return (audio_array, sample_rate, info).

    Args:
        path:       Absolute path to audio file
        target_sr:  If specified, resample to this sample rate
        mono:       If True, convert to mono

    Returns:
        (y: float32 array, sr: int, info: AudioInfo)
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")

    info = AudioInfo(
        path=path,
        filename=os.path.basename(path),
        format=os.path.splitext(path)[-1].lstrip(".").upper(),
    )

    result = _load_with_soundfile(path, info)
    if result is None:
        y, sr = _load_with_librosa(path, info)
    else:
        y, sr = result

    # Convert to mono
    if mono and y.ndim == 2:
        y = y.mean(axis=1)

    y = y.astype(np.float32)

    # Resample if requested
    if target_sr and sr != target_sr:
        import librosa
        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        sr = target_sr

    info.sample_rate = sr
    info.channels = 1 if mono else (y.shape[1] if y.ndim == 2 else 1)
    info.duration = len(y) / sr

    return y, sr, info


def _load_with_soundfile(path: str, info: AudioInfo) -> Optional[Tuple[np.ndarray, int]]:
    """Try loading with soundfile (fast, lossless)."""
    try:
        import soundfile as sf
        data, sr = sf.read(path, always_2d=True)
        info.channels = data.shape[1]
        info.sample_rate = sr
        # Try to get bit depth
        sfinfo = sf.info(path)
        subtype = sfinfo.subtype
        if "16" in subtype:
            info.bit_depth = 16
        elif "24" in subtype:
            info.bit_depth = 24
        elif "32" in subtype:
            info.bit_depth = 32
        return data, sr
    except Exception:
        return None


def _load_with_librosa(path: str, info: AudioInfo) -> Tuple[np.ndarray, int]:
    """Load with librosa (handles MP3, M4A via audioread/ffmpeg)."""
    import librosa
    y, sr = librosa.load(path, sr=None, mono=False)
    if y.ndim == 1:
        y = y[:, np.newaxis]
    info.channels = y.shape[0] if y.ndim == 2 else 1
    info.sample_rate = sr
    if y.ndim == 2:
        y = y.T  # -> (samples, channels)
    return y, sr
