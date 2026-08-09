"""
NeuroDrums AI - Audio Export Module.

Handles:
  - Full mix export (all lanes combined)
  - Individual stem exports (one file per lane)
  - Sample rate conversion
  - Bit depth selection (16/24/32-bit float)
  - Stereo output
"""
from __future__ import annotations
import os
import numpy as np
import soundfile as sf
from typing import Dict, Optional, Callable, List

from core.constants import LANE_NAMES


SAMPLE_RATES = [44100, 48000, 88200, 96000]
BIT_DEPTHS = [16, 24, 32]


def export_mix(
    y: np.ndarray,
    sr: int,
    output_path: str,
    target_sr: int = 44100,
    bit_depth: int = 24,
    normalize: bool = True,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> str:
    """
    Export a full audio mix to WAV.

    Args:
        y:            float32 audio array (mono)
        sr:           source sample rate
        output_path:  destination file path
        target_sr:    output sample rate
        bit_depth:    16 / 24 / 32
        normalize:    apply peak normalization if peak > 0.98
        progress_cb:  optional progress callback

    Returns:
        output_path
    """
    if progress_cb:
        progress_cb(0.1)

    audio = _prepare(y, sr, target_sr, normalize)

    if progress_cb:
        progress_cb(0.8)

    _write(audio, target_sr, output_path, bit_depth)

    if progress_cb:
        progress_cb(1.0)

    return output_path


def export_stems(
    stem_audio: Dict[str, np.ndarray],
    sr: int,
    output_dir: str,
    target_sr: int = 44100,
    bit_depth: int = 24,
    selected_lanes: Optional[List[str]] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[str]:
    """
    Export individual lane stems as separate WAV files.

    Args:
        stem_audio:      {lane_name: audio_array}
        sr:              source sample rate
        output_dir:      directory for output files
        target_sr:       output sample rate
        bit_depth:       16 / 24 / 32
        selected_lanes:  if provided, only export these lanes
        progress_cb:     callback(fraction, lane_name)

    Returns:
        List of written file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    lanes = selected_lanes or LANE_NAMES
    written = []

    for i, lane in enumerate(lanes):
        if lane not in stem_audio:
            continue
        audio = _prepare(stem_audio[lane], sr, target_sr, normalize=True)
        safe_name = lane.replace(" ", "_").lower()
        path = os.path.join(output_dir, f"{safe_name}.wav")
        _write(audio, target_sr, path, bit_depth)
        written.append(path)
        if progress_cb:
            progress_cb((i + 1) / max(len(lanes), 1), lane)

    return written


def _prepare(
    y: np.ndarray,
    sr: int,
    target_sr: int,
    normalize: bool,
) -> np.ndarray:
    """Resample, normalize, convert to float32."""
    audio = np.asarray(y, dtype=np.float32)

    # Resample if needed
    if sr != target_sr:
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)

    # Peak normalize
    if normalize:
        peak = np.max(np.abs(audio))
        if peak > 0.98:
            audio = audio * (0.98 / peak)

    return audio


def _write(audio: np.ndarray, sr: int, path: str, bit_depth: int) -> None:
    """Write audio to WAV file with correct bit depth."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    subtype_map = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}
    subtype = subtype_map.get(bit_depth, "PCM_24")
    # Write stereo (duplicate mono channel)
    stereo = np.stack([audio, audio], axis=-1) if audio.ndim == 1 else audio
    sf.write(path, stereo, sr, subtype=subtype)
