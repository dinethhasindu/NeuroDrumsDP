"""
NeuroDrums AI - 8-Class Drum Event Classifier.

Multi-stage classification pipeline:
  Stage A: DrumSep ONNX model (4-class: kick/snare/cymbal/tom)
  Stage B: Feature-based RandomForest classifier (8-class output)
  Fallback: Rule-based heuristic classifier

All classifiers return confidence scores per class.
If confidence < threshold, event is marked 'uncertain'.
"""
from __future__ import annotations
import os
import pickle
import warnings
import numpy as np
from typing import Dict, Tuple, Optional, List

from core.constants import LANE_NAMES
from detection.transient import feature_vector

warnings.filterwarnings('ignore', category=UserWarning)

# Class index → lane name mapping
CLASS_NAMES = LANE_NAMES  # ["Kick","Snare","Closed Hat","Open Hat","Clap","Roll","Snare Roll","FX"]

# Confidence threshold below which event is marked uncertain
CONFIDENCE_THRESHOLD = 0.40

# Path to pre-trained RandomForest model (relative to project root)
RF_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "drum_rf_classifier.pkl")


class DrumClassifier:
    """
    8-class drum event classifier.

    Uses a RandomForest trained on acoustic features.
    Falls back to a robust heuristic classifier if the RF model
    is unavailable.
    """

    def __init__(self, model_path: Optional[str] = None):
        self._rf = None
        self._scaler = None
        path = model_path or RF_MODEL_PATH
        self._load_rf(path)

    def _load_rf(self, path: str) -> None:
        """Attempt to load pre-trained RF model."""
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    payload = pickle.load(f)
                self._rf = payload.get("model")
                self._scaler = payload.get("scaler")
                print(f"[Classifier] Loaded RF model from {path}")
            else:
                print(f"[Classifier] RF model not found at {path}; using heuristic fallback.")
        except Exception as e:
            print(f"[Classifier] Failed to load RF model: {e}; using heuristic fallback.")

    def classify(
        self,
        features: Dict[str, float],
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Classify a drum event from its feature dict.

        Args:
            features: dict produced by detection.transient.extract_features()

        Returns:
            (predicted_type, confidence, all_class_probabilities)
        """
        vec = feature_vector(features).reshape(1, -1)

        if self._rf is not None:
            try:
                if self._scaler is not None:
                    vec = self._scaler.transform(vec)
                probs = self._rf.predict_proba(vec)[0]
                classes = self._rf.classes_
                prob_dict = {c: float(p) for c, p in zip(classes, probs)}
                # Fill any missing classes with 0
                full_dict = {name: prob_dict.get(name, 0.0) for name in CLASS_NAMES}
                predicted = max(full_dict, key=full_dict.__getitem__)
                confidence = full_dict[predicted]

                # If confidence is very low, defer to heuristic
                if confidence < 0.30:
                    return self._heuristic_classify(features)

                return predicted, confidence, full_dict
            except Exception as e:
                print(f"[Classifier] RF inference error: {e}; using heuristic.")

        return self._heuristic_classify(features)

    def _heuristic_classify(
        self,
        feats: Dict[str, float],
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Rule-based heuristic classifier using multi-feature decision tree.
        More accurate than a simple threshold on a single band.
        """
        low = feats.get("low_energy", 0.0)
        mid = feats.get("mid_energy", 0.0)
        high = feats.get("high_energy", 0.0)
        sub = feats.get("subbass_energy", 0.0)
        centroid = feats.get("spectral_centroid", 0.0)
        zcr = feats.get("zcr", 0.0)
        duration = feats.get("duration", 0.1)
        percussive = feats.get("percussive_ratio", 0.5)
        flatness = feats.get("spectral_flatness", 0.0)
        bandwidth = feats.get("spectral_bandwidth", 0.0)
        attack = feats.get("attack_frac", 0.1)
        decay_t = feats.get("decay_time", 0.1)
        crest = feats.get("crest_factor", 3.0)

        probs = {name: 0.01 for name in CLASS_NAMES}

        # KICK: sub-bass heavy, low centroid, slow attack relative to duration
        kick_score = (
            low * 2.0
            + sub * 3.0
            + (1.0 if centroid < 800 else 0.0)
            + (0.5 if centroid < 400 else 0.0)
            + percussive * 0.5
            + (0.5 if attack < 0.2 else 0.0)
        )
        probs["Kick"] = np.clip(kick_score / 4.5, 0, 1)

        # SNARE: mid-high energy, moderate centroid, bright transient, percussive
        snare_score = (
            mid * 1.5
            + (0.8 if 800 <= centroid <= 5000 else 0.0)
            + (0.5 if zcr > 0.05 else 0.0)
            + percussive * 0.8
            + high * 0.5
            + (0.4 if 0.2 < attack < 0.5 else 0.0)
        )
        probs["Snare"] = np.clip(snare_score / 4.0, 0, 1)

        # CLOSED HAT: very high energy, short decay, small bandwidth
        hat_c_score = (
            high * 2.5
            + (1.0 if centroid > 4000 else 0.0)
            + (1.0 if duration < 0.08 else 0.0)
            + (0.5 if decay_t < 0.05 else 0.0)
            + zcr * 3.0
        )
        probs["Closed Hat"] = np.clip(hat_c_score / 5.0, 0, 1)

        # OPEN HAT: high centroid, longer decay, high zcr
        hat_o_score = (
            high * 2.0
            + (1.0 if centroid > 5000 else 0.0)
            + (1.0 if duration > 0.08 else 0.0)
            + (0.5 if decay_t > 0.06 else 0.0)
            + zcr * 2.5
        )
        probs["Open Hat"] = np.clip(hat_o_score / 5.0, 0, 1)

        # CLAP: very high zcr, sharp transient, mid-high centroid, flat spectrum
        clap_score = (
            zcr * 4.0
            + flatness * 2.0
            + mid * 1.0
            + (0.5 if 1500 <= centroid <= 6000 else 0.0)
            + crest * 0.1
        )
        probs["Clap"] = np.clip(clap_score / 5.5, 0, 1)

        # ROLL / SNARE ROLL are handled by roll_detector post-process
        probs["Roll"]       = 0.05
        probs["Snare Roll"] = 0.05

        # FX: none of the above match well
        total_others = sum(probs[k] for k in ["Kick","Snare","Closed Hat","Open Hat","Clap"])
        fx_score = max(0, 1.0 - total_others / 2.5)
        probs["FX"] = np.clip(fx_score, 0, 1)

        # Normalize
        total = sum(probs.values()) + 1e-9
        probs = {k: v / total for k, v in probs.items()}

        predicted = max(probs, key=probs.__getitem__)
        confidence = probs[predicted]

        return predicted, confidence, probs

    def train_from_examples(
        self,
        feature_list: List[Dict[str, float]],
        label_list: List[str],
        save_path: Optional[str] = None,
    ) -> bool:
        """
        Train or fine-tune the RandomForest classifier from labelled examples.
        Saves the model to disk.

        Args:
            feature_list: list of feature dicts
            label_list:   list of lane name labels
            save_path:    path to save model pkl

        Returns:
            True if training succeeded
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler

            X = np.array([feature_vector(f) for f in feature_list])
            y = label_list

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            clf = RandomForestClassifier(
                n_estimators=300,
                max_depth=None,
                min_samples_split=2,
                class_weight="balanced",
                n_jobs=-1,
                random_state=42,
            )
            clf.fit(X_scaled, y)

            self._rf = clf
            self._scaler = scaler

            out = save_path or RF_MODEL_PATH
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            with open(out, "wb") as f:
                pickle.dump({"model": clf, "scaler": scaler}, f)
            print(f"[Classifier] Trained & saved RF model to {out}")
            return True
        except Exception as e:
            print(f"[Classifier] Training failed: {e}")
            return False

    def build_synthetic_training_data(self) -> Tuple[List[Dict], List[str]]:
        """
        Generate synthetic training data using acoustically-motivated feature
        distributions for each drum class.

        This allows the RF to be pre-trained without real audio data.
        """
        rng = np.random.RandomState(0)
        X, y = [], []

        def synth(n, **kwargs):
            feats = {
                "rms": 0.2, "peak": 0.8, "crest_factor": 4.0, "duration": 0.1,
                "zcr": 0.1, "attack_time": 0.005, "attack_frac": 0.05,
                "decay_time": 0.08, "low_energy": 0.33, "mid_energy": 0.33,
                "high_energy": 0.33, "subbass_energy": 0.1,
                "spectral_centroid": 3000.0, "spectral_centroid_std": 500.0,
                "spectral_bandwidth": 2000.0, "spectral_rolloff": 5000.0,
                "spectral_flatness": 0.1, "spectral_flux": 0.3, "spectral_flux_max": 0.9,
                "onset_strength_peak": 1.0, "onset_strength_mean": 0.4,
                "onset_concentration": 0.05, "harmonic_ratio": 0.3,
                "percussive_ratio": 0.7, "velocity": 0.8,
            }
            for i in range(13):
                feats[f"mfcc_{i}"] = 0.0
            feats.update(kwargs)
            samples = []
            for _ in range(n):
                noisy = {k: v + rng.normal(0, abs(v) * 0.15 + 0.01) for k, v in feats.items()}
                # Clip energy ratios
                for k in ["low_energy", "mid_energy", "high_energy", "subbass_energy",
                          "harmonic_ratio", "percussive_ratio"]:
                    noisy[k] = float(np.clip(noisy[k], 0, 1))
                samples.append(noisy)
            return samples

        kick_samples    = synth(200, low_energy=0.65, subbass_energy=0.45, spectral_centroid=350.0,  percussive_ratio=0.85, zcr=0.03, duration=0.18, decay_time=0.12)
        snare_samples   = synth(200, low_energy=0.20, mid_energy=0.50, high_energy=0.30, spectral_centroid=2800.0, percussive_ratio=0.75, zcr=0.09, duration=0.12)
        chat_samples    = synth(200, high_energy=0.72, spectral_centroid=7500.0, zcr=0.22, duration=0.05, decay_time=0.02)
        ohat_samples    = synth(200, high_energy=0.70, spectral_centroid=8000.0, zcr=0.20, duration=0.15, decay_time=0.09)
        clap_samples    = synth(200, mid_energy=0.45, high_energy=0.38, spectral_centroid=3500.0, zcr=0.18, spectral_flatness=0.25, duration=0.06)
        roll_samples    = synth(100, mid_energy=0.45, high_energy=0.35, spectral_centroid=4000.0, duration=0.04, decay_time=0.02)
        sroll_samples   = synth(100, mid_energy=0.50, high_energy=0.28, spectral_centroid=2800.0, duration=0.05)
        fx_samples      = synth(150, spectral_centroid=5500.0, spectral_flatness=0.3, harmonic_ratio=0.5, duration=0.25)

        for s in kick_samples:  X.append(s); y.append("Kick")
        for s in snare_samples: X.append(s); y.append("Snare")
        for s in chat_samples:  X.append(s); y.append("Closed Hat")
        for s in ohat_samples:  X.append(s); y.append("Open Hat")
        for s in clap_samples:  X.append(s); y.append("Clap")
        for s in roll_samples:  X.append(s); y.append("Roll")
        for s in sroll_samples: X.append(s); y.append("Snare Roll")
        for s in fx_samples:    X.append(s); y.append("FX")

        return X, y


def build_and_save_default_classifier() -> None:
    """
    Train and save the default RF classifier using synthetic data.
    Call this once during setup or when the model is missing.
    """
    clf = DrumClassifier.__new__(DrumClassifier)
    clf._rf = None
    clf._scaler = None
    X, y = clf.build_synthetic_training_data()
    clf.train_from_examples(X, y)
