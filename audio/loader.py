from __future__ import annotations
import os
import numpy as np
from core.models import AudioInfo

def load_audio(path: str, target_sr: int | None = None, mono: bool = True):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    info = AudioInfo(path=path, filename=os.path.basename(path), format=os.path.splitext(path)[1].lstrip('.').upper())
    try:
        import soundfile as sf
        data, sr = sf.read(path, always_2d=True, dtype='float32')
        info.channels = data.shape[1]
        try:
            sub = sf.info(path).subtype
            info.bit_depth = 32 if '32' in sub else 24 if '24' in sub else 16
        except Exception:
            pass
        y = data.mean(axis=1) if mono else data
    except Exception:
        import librosa
        y, sr = librosa.load(path, sr=None, mono=mono)
        y = np.asarray(y, dtype=np.float32)
        if not mono and y.ndim == 1:
            y = y[:, None]
    if target_sr and int(sr) != int(target_sr):
        import librosa
        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr).astype(np.float32)
        sr = target_sr
    y = np.asarray(y, dtype=np.float32)
    info.sample_rate = int(sr)
    info.channels = 1 if mono else (y.shape[1] if y.ndim == 2 else 1)
    info.duration = len(y) / float(sr)
    return y, int(sr), info
