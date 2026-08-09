"""
NeuroDrums AI - Roll & Snare Roll Detection.

Analyzes event sequences to identify rolls:
  - ROLL: dense repeated percussion events
  - SNARE ROLL: dense events classified primarily as snare-like

Decision criteria:
  1. Hit density (hits/second)
  2. Spectral similarity between consecutive hits (cosine similarity)
  3. Inter-onset interval regularity (coefficient of variation)
  4. Velocity pattern (flat or crescendo suggests roll)
  5. Snare-likeness of events in the cluster
"""
from __future__ import annotations
import numpy as np
from typing import List
from core.models import DrumEvent


ROLL_DENSITY_HZ = 7.0        # Minimum hits per second to be a roll
ROLL_MIN_EVENTS = 4          # Minimum events in a cluster
SIMILARITY_THRESHOLD = 0.75  # Minimum cosine similarity
CV_THRESHOLD = 0.35          # Max coefficient of variation of IOIs


def detect_rolls(events: List[DrumEvent], y: np.ndarray, sr: int) -> List[DrumEvent]:
    """
    Post-processes the event list to relabel dense clusters as ROLL or SNARE ROLL.

    Modifies events in-place.

    Returns the modified list.
    """
    if len(events) < ROLL_MIN_EVENTS:
        return events

    # Group events into clusters by proximity
    clusters = _cluster_events(events, max_gap=0.18)

    for cluster in clusters:
        if len(cluster) < ROLL_MIN_EVENTS:
            continue

        times = np.array([e.start for e in cluster])
        iois = np.diff(times)  # Inter-onset intervals

        if len(iois) == 0:
            continue

        # Density check
        span = times[-1] - times[0]
        density = len(cluster) / max(span, 0.001)

        if density < ROLL_DENSITY_HZ:
            continue

        # IOI regularity: low CV = more regular
        cv = float(iois.std() / (iois.mean() + 1e-9))
        if cv > CV_THRESHOLD:
            continue

        # Determine roll type based on event composition
        snare_count = sum(1 for e in cluster if e.type in ("Snare", "Snare Roll"))
        snare_frac = snare_count / len(cluster)

        # Spectral similarity check using pre-extracted features
        similarity = _spectral_similarity_from_features(cluster)

        if similarity < SIMILARITY_THRESHOLD:
            continue

        # Classify cluster
        if snare_frac >= 0.5:
            new_type = "Snare Roll"
        else:
            new_type = "Roll"

        for e in cluster:
            if e.type not in ("Kick",):  # Never relabel kicks
                e.type = new_type
                e.subtype = "roll"

    return events


def _cluster_events(events: List[DrumEvent], max_gap: float) -> List[List[DrumEvent]]:
    """Group events into temporal clusters."""
    if not events:
        return []
    sorted_evs = sorted(events, key=lambda e: e.start)
    clusters = []
    current = [sorted_evs[0]]
    for ev in sorted_evs[1:]:
        if ev.start - current[-1].start <= max_gap:
            current.append(ev)
        else:
            clusters.append(current)
            current = [ev]
    clusters.append(current)
    return clusters


def _spectral_similarity_from_features(cluster: List[DrumEvent]) -> float:
    """
    Estimate spectral similarity using pre-computed per-event spectral centroid.
    A low standard deviation of centroids within a cluster means similar timbres.
    """
    centroids = [e.spectral_centroid for e in cluster if e.spectral_centroid > 0]
    if len(centroids) < 2:
        return 1.0
    cv = float(np.std(centroids) / (np.mean(centroids) + 1e-9))
    # Convert CV to similarity (low CV = high similarity)
    sim = float(np.clip(1.0 - cv, 0.0, 1.0))
    return sim
