from __future__ import annotations
import numpy as np
import librosa
from core.constants import LANE_NAMES
from core.models import Event

class DrumDetector:
    """Conservative DSP fallback detector. It creates candidates first, then classifies them."""
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.ort = None
        if model_path:
            try:
                import onnxruntime as ort
                self.ort = ort
            except Exception:
                self.ort = None

    def detect(self, y, sr):
        y = np.asarray(y, dtype=np.float32)
        if len(y) < 512:
            return []
        hop = 256
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        if len(onset_env) == 0:
            return []
        frames = librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=sr, hop_length=hop,
            backtrack=True, pre_max=8, post_max=8,
            pre_avg=16, post_avg=16, delta=0.18, wait=2,
        )
        times = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
        events = []
        for t in times:
            a = max(0, int((t - 0.010) * sr))
            b = min(len(y), int((t + 0.180) * sr))
            x = y[a:b]
            if len(x) < 128:
                continue
            typ, confidence = self._classify(x, sr)
            rms = float(np.sqrt(np.mean(x * x)) + 1e-9)
            events.append(Event(
                time=float(t), type=typ,
                strength=float(min(1.5, rms * 20.0)),
                confidence=float(confidence),
                duration=float(min(0.22, len(x) / sr)),
            ))
        self._group_rolls(events)
        return events

    def _classify(self, x, sr):
        spec = np.abs(librosa.stft(x, n_fft=1024, hop_length=256))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
        e = np.mean(spec, axis=1) + 1e-12
        low = float(e[freqs < 180].sum())
        mid = float(e[(freqs >= 180) & (freqs < 2500)].sum())
        high = float(e[freqs >= 2500].sum())
        total = low + mid + high
        lowp, midp, highp = low/total, mid/total, high/total
        centroid = float(librosa.feature.spectral_centroid(S=spec, sr=sr).mean())
        zcr = float(librosa.feature.zero_crossing_rate(x).mean())
        duration = len(x) / sr
        scores = {
            "Kick": min(1.0, 0.45*lowp + max(0.0, (900-centroid)/1800)),
            "Snare": min(1.0, 0.40*midp + 0.30*highp + min(0.3, zcr*1.5)),
            "Closed Hat": min(1.0, 0.75*highp + max(0.0, (centroid-3500)/6000)),
            "Open Hat": min(1.0, 0.60*highp + (0.30 if duration > 0.055 else 0.0)),
            "Clap": min(1.0, 0.45*midp + 0.40*highp + min(0.2, zcr)),
            "FX": min(1.0, 0.35*highp + 0.20*midp),
        }
        # Keep the original conservative ordering for ambiguous material.
        if lowp > 0.48 and centroid < 900:
            typ = "Kick"
        elif highp > 0.60 and centroid > 5500:
            typ = "Open Hat" if duration > 0.055 else "Closed Hat"
        elif midp > 0.40 and highp > 0.20 and zcr > 0.08:
            typ = "Snare"
        elif midp > 0.48 and highp > 0.30:
            typ = "Clap"
        elif highp > 0.45:
            typ = "Closed Hat"
        else:
            typ = "FX"
        confidence = max(0.35, min(0.98, scores.get(typ, 0.45)))
        return typ, confidence

    def _group_rolls(self, events):
        for i, event in enumerate(events):
            near = 0
            for j in range(max(0, i-5), min(len(events), i+6)):
                if i == j:
                    continue
                dt = events[j].time - event.time
                if 0 < dt < 0.14:
                    near += 1
            if near >= 2 and event.type == "Snare":
                event.type = "Snare Roll"
                event.confidence = min(0.99, event.confidence + 0.10)
            elif near >= 3 and event.type in ("Closed Hat", "Snare"):
                event.type = "Roll"
                event.confidence = min(0.99, event.confidence + 0.08)
