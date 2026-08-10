from __future__ import annotations
import os
import pickle
import numpy as np
from core.constants import LANE_NAMES
from detection.transient import feature_vector


class DrumClassifier:
    """Uses a trained RF model when present; otherwise deterministic analysis fallback."""

    def __init__(self, model_path='models/drum_rf_classifier.pkl'):
        self.rf = None
        self.scaler = None
        self.mode = 'Analysis Fallback'
        self.model_name = 'None'
        if os.path.isfile(model_path):
            try:
                with open(model_path, 'rb') as f:
                    p = pickle.load(f)
                self.rf = p.get('model')
                self.scaler = p.get('scaler')
                self.mode = 'Random Forest'
                self.model_name = os.path.basename(model_path)
            except Exception:
                pass

    def classify(self, f):
        if self.rf is not None:
            try:
                v = feature_vector(f).reshape(1, -1)
                if self.scaler is not None:
                    v = self.scaler.transform(v)
                probs = self.rf.predict_proba(v)[0]
                names = list(self.rf.classes_)
                d = {n: 0.0 for n in LANE_NAMES}
                for n, p in zip(names, probs):
                    if n in d:
                        d[n] = float(p)
                k = max(d, key=d.get)
                return k, d[k], d
            except Exception:
                pass
        low, mid, high, sub = f['low_energy'], f['mid_energy'], f['high_energy'], f['subbass_energy']
        c = f['spectral_centroid']
        z = f['zcr']
        dur = f['duration']
        flat = f['spectral_flatness']
        flux = f.get('spectral_flux', 0.0)
        attack = f.get('attack_frac', 0.15)
        scores = {n: 0.03 for n in LANE_NAMES}
        scores['Kick'] = 0.15 + 1.7 * low + 1.0 * sub + max(0, 0.8 - c / 1600)
        scores['Snare'] = 0.20 + 1.0 * mid + 0.8 * high + z * 1.8
        scores['Closed Hat'] = 0.15 + 1.9 * high + max(0, c / 9000) + flux * 0.5
        scores['Open Hat'] = 0.10 + 1.5 * high + 0.8 * min(1, dur / 0.12) + c / 12000
        scores['Clap'] = 0.10 + 1.1 * mid + 0.9 * high + 0.4 * z
        scores['FX'] = 0.08 + 0.7 * high + 0.4 * flat + 0.3 * min(1, c / 7000)
        if attack < 0.08 and high > 0.35:
            scores['Closed Hat'] += 0.15
        if max(scores.values()) < 0.65:
            scores['FX'] += 0.2
        total = sum(max(0, v) for v in scores.values())
        probs = {k: max(0, v) / total for k, v in scores.items()}
        k = max(probs, key=probs.get)
        return k, probs[k], probs
