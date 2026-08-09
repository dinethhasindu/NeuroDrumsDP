"""
NeuroDrums AI - Multi-Resolution Waveform Peak Cache.

Generates peak data at 5 zoom levels for smooth waveform rendering.
Cache files stored in: cache/{stem}_peaks.npz

Levels (decimation factors):
  Level 0:  64x  (overview)
  Level 1: 256x  (medium zoom)
  Level 2: 512x  (close zoom)
  Level 3: 1024x (event-level)
  Level 4: 4096x (transient-level)

Each level stores: min_peaks, max_peaks arrays.
"""
from __future__ import annotations
import os
import numpy as np
from typing import List, Tuple, Optional


DECIMATIONS = [64, 256, 512, 1024, 4096]
CACHE_DIR = "cache"


class WaveformCache:
    """
    Multi-resolution waveform peak cache.
    """

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._peaks: List[Tuple[np.ndarray, np.ndarray]] = []  # (min, max) per level
        self._sr: int = 44100
        self._n_samples: int = 0
        self._duration: float = 0.0

    def build(
        self,
        y: np.ndarray,
        sr: int,
        cache_key: Optional[str] = None,
        progress_cb=None,
    ) -> None:
        """
        Build peak cache from audio array.

        Args:
            y:          mono float32 audio
            sr:         sample rate
            cache_key:  used for disk cache filename
            progress_cb: optional progress callback
        """
        self._sr = sr
        self._n_samples = len(y)
        self._duration = len(y) / sr
        self._peaks = []

        # Check disk cache
        if cache_key:
            cached = self._load_cache(cache_key)
            if cached is not None:
                self._peaks = cached
                if progress_cb:
                    progress_cb(1.0)
                return

        # Build peaks for each level
        total = len(DECIMATIONS)
        for i, dec in enumerate(DECIMATIONS):
            min_peaks, max_peaks = self._build_level(y, dec)
            self._peaks.append((min_peaks, max_peaks))
            if progress_cb:
                progress_cb((i + 1) / total)

        # Save to disk
        if cache_key:
            self._save_cache(cache_key)

    def _build_level(
        self, y: np.ndarray, decimation: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute min/max peaks with given decimation factor."""
        n = len(y)
        # Pad to multiple of decimation
        pad = (-n % decimation)
        if pad > 0:
            y_padded = np.pad(y, (0, pad), mode='constant')
        else:
            y_padded = y
        chunks = y_padded.reshape(-1, decimation)
        min_p = chunks.min(axis=1).astype(np.float32)
        max_p = chunks.max(axis=1).astype(np.float32)
        return min_p, max_p

    def get_peaks(
        self,
        t_start: float,
        t_end: float,
        pixel_width: int,
        zoom: float = 1.0,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Return peak data for a given time window at appropriate resolution.

        Returns:
            (times, min_peaks, max_peaks) - all same length
        """
        if not self._peaks or self._duration == 0:
            empty = np.array([], dtype=np.float32)
            return empty, empty, empty

        # Choose best resolution level
        visible_samples = (t_end - t_start) * self._sr
        pixels_per_sample = pixel_width / max(visible_samples, 1)
        target_decimation = max(1, int(1.0 / max(pixels_per_sample, 1e-9)))

        # Find closest level
        best_level = 0
        best_diff = abs(DECIMATIONS[0] - target_decimation)
        for i, dec in enumerate(DECIMATIONS):
            diff = abs(dec - target_decimation)
            if diff < best_diff:
                best_diff = diff
                best_level = i

        dec = DECIMATIONS[best_level]
        min_p, max_p = self._peaks[best_level]

        # Slice to time window
        start_chunk = int(t_start * self._sr / dec)
        end_chunk = int(np.ceil(t_end * self._sr / dec)) + 1
        start_chunk = max(0, start_chunk)
        end_chunk = min(len(min_p), end_chunk)

        sliced_min = min_p[start_chunk:end_chunk]
        sliced_max = max_p[start_chunk:end_chunk]

        # Build time axis
        chunk_duration = dec / self._sr
        times = np.arange(len(sliced_min)) * chunk_duration + start_chunk * chunk_duration
        times = times.astype(np.float32)

        return times, sliced_min, sliced_max

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def sample_rate(self) -> int:
        return self._sr

    def _cache_path(self, key: str) -> str:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in key)
        return os.path.join(self.cache_dir, f"{safe}_peaks.npz")

    def _save_cache(self, key: str) -> None:
        try:
            path = self._cache_path(key)
            arrays = {}
            for i, (mn, mx) in enumerate(self._peaks):
                arrays[f"min_{i}"] = mn
                arrays[f"max_{i}"] = mx
            arrays["sr"] = np.array([self._sr])
            arrays["n_samples"] = np.array([self._n_samples])
            np.savez_compressed(path, **arrays)
        except Exception as e:
            print(f"[WaveformCache] Could not save cache: {e}")

    def _load_cache(self, key: str) -> Optional[List[Tuple[np.ndarray, np.ndarray]]]:
        try:
            path = self._cache_path(key)
            if not os.path.exists(path):
                return None
            data = np.load(path)
            peaks = []
            for i in range(len(DECIMATIONS)):
                if f"min_{i}" not in data:
                    return None
                peaks.append((data[f"min_{i}"], data[f"max_{i}"]))
            self._sr = int(data["sr"][0])
            self._n_samples = int(data["n_samples"][0])
            self._duration = self._n_samples / self._sr
            return peaks
        except Exception:
            return None
