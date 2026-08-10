from __future__ import annotations
import hashlib, os
import numpy as np

class WaveformCache:
    """Multi-resolution min/max envelope cache. Never requires the original audio at paint time."""
    DECIMATIONS = (32, 128, 512, 2048, 8192)
    def __init__(self, cache_dir='cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._levels = []
        self._sr = 44100
        self._n = 0

    @property
    def duration(self):
        return self._n / self._sr if self._sr else 0.0

    @property
    def sample_rate(self): return self._sr

    def _key(self, key):
        return hashlib.sha1(os.path.abspath(str(key)).encode('utf-8')).hexdigest()[:20]

    def _path(self, key): return os.path.join(self.cache_dir, self._key(key) + '_waveform.npz')

    def build(self, y, sr, cache_key=None, progress_cb=None, force=False):
        y = np.asarray(y, dtype=np.float32).reshape(-1)
        self._sr, self._n = int(sr), int(len(y))
        self._levels = []
        if cache_key and not force:
            if self._load(cache_key):
                if progress_cb: progress_cb(1.0)
                return
        for i, dec in enumerate(self.DECIMATIONS):
            n = int(np.ceil(len(y) / dec))
            pad = n * dec - len(y)
            z = np.pad(y, (0, pad)) if pad else y
            chunks = z.reshape(n, dec)
            self._levels.append((chunks.min(1).astype(np.float32), chunks.max(1).astype(np.float32)))
            if progress_cb: progress_cb((i + 1) / len(self.DECIMATIONS))
        if cache_key: self._save(cache_key)

    def _save(self, key):
        try:
            data = {'sr': np.array([self._sr]), 'n': np.array([self._n])}
            for i, (mn, mx) in enumerate(self._levels):
                data[f'mn{i}'], data[f'mx{i}'] = mn, mx
            np.savez_compressed(self._path(key), **data)
        except Exception:
            pass

    def _load(self, key):
        try:
            p = self._path(key)
            if not os.path.exists(p): return False
            with np.load(p, allow_pickle=False) as d:
                sr, n = int(d['sr'][0]), int(d['n'][0])
                if sr != self._sr or n != self._n: return False
                levels = []
                for i in range(len(self.DECIMATIONS)):
                    if f'mn{i}' not in d or f'mx{i}' not in d: return False
                    levels.append((d[f'mn{i}'], d[f'mx{i}']))
            self._levels = levels
            return True
        except Exception:
            return False

    def get_peaks(self, t0, t1, pixel_width, zoom=120.0):
        if not self._levels or self._n == 0: return np.empty(0), np.empty(0), np.empty(0)
        t0, t1 = max(0.0, float(t0)), min(self.duration, max(float(t0), float(t1)))
        visible = max(1, int((t1-t0) * self._sr))
        target = max(1, visible // max(1, int(pixel_width)))
        idx = min(range(len(self.DECIMATIONS)), key=lambda i: abs(self.DECIMATIONS[i]-target))
        dec = self.DECIMATIONS[idx]
        mn, mx = self._levels[idx]
        a = max(0, int(t0*self._sr/dec)-2)
        b = min(len(mn), int(np.ceil(t1*self._sr/dec))+3)
        mn, mx = mn[a:b], mx[a:b]
        times = (np.arange(len(mn), dtype=np.float32)+a) * (dec/self._sr)
        return times, mn, mx
