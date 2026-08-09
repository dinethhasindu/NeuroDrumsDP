"""
NeuroDrums AI - Confidence Scoring.

Provides utilities for:
  - Interpreting per-class probability vectors
  - Applying entropy-based confidence calibration
  - Generating uncertainty labels for UI display
"""
from __future__ import annotations
import numpy as np
from typing import Dict, Tuple


def calibrate_confidence(
    raw_probs: Dict[str, float],
    confidence_threshold: float = 0.40,
) -> Tuple[str, float, bool]:
    """
    Given a class probability dict, return the predicted class,
    calibrated confidence, and whether the event is 'uncertain'.

    Args:
        raw_probs:            {class_name: probability} from classifier
        confidence_threshold: events below this are marked uncertain

    Returns:
        (predicted_class, confidence, is_uncertain)
    """
    if not raw_probs:
        return "FX", 0.0, True

    predicted = max(raw_probs, key=raw_probs.__getitem__)
    top_prob = float(raw_probs[predicted])

    # Entropy-based uncertainty: high entropy = low confidence
    probs = np.array(list(raw_probs.values()), dtype=np.float64)
    probs = np.clip(probs, 1e-9, 1.0)
    probs = probs / probs.sum()
    entropy = -float(np.sum(probs * np.log(probs)))
    max_entropy = float(np.log(len(probs)))
    entropy_ratio = entropy / max(max_entropy, 1e-9)

    # Calibrated confidence: blend top probability with inverse entropy
    calibrated = float(top_prob * (1.0 - 0.5 * entropy_ratio))
    calibrated = float(np.clip(calibrated, 0.0, 1.0))

    is_uncertain = calibrated < confidence_threshold
    return predicted, calibrated, is_uncertain


def confidence_color(confidence: float) -> str:
    """
    Return a hex color string for a given confidence value.
    """
    if confidence >= 0.75:
        return "#2dc653"  # green
    elif confidence >= 0.50:
        return "#ffbe0b"  # yellow
    else:
        return "#ff4d6d"  # red


def confidence_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "High"
    elif confidence >= 0.50:
        return "Medium"
    else:
        return "Low"
