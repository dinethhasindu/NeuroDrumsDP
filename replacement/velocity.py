"""
NeuroDrums AI - Replacement Velocity Module.

Scales replacement sample velocity (amplitude) based on the original event's velocity.
"""
from __future__ import annotations
import numpy as np

def apply_velocity(
    audio: np.ndarray,
    velocity: float,
    match_velocity: bool = True,
    curve: str = "linear",
    volume_db: float = 0.0,
) -> np.ndarray:
    """
    Scale audio amplitude based on event velocity and volume offset.

    Args:
        audio:          float32 audio array
        velocity:       0.0 to 1.0
        match_velocity: whether to apply the velocity scaling
        curve:          "linear", "soft", or "hard"
        volume_db:      static volume offset in dB
    """
    out = audio.copy()

    # Apply volume offset (dB to linear)
    if volume_db != 0.0:
        gain = 10.0 ** (volume_db / 20.0)
        out *= gain

    if not match_velocity:
        return out

    # Clamp velocity
    vel = np.clip(velocity, 0.0, 1.0)

    # Apply curve
    if curve == "soft":
        vel = np.sqrt(vel)
    elif curve == "hard":
        vel = vel ** 2
    # linear does nothing

    # Prevent total silence for very quiet notes, maintain a minimum floor (e.g. 0.1)
    # Actually, if the model predicts a quiet velocity, we might want it quiet.
    # Let's map 0.0-1.0 to an appropriate dynamic range, e.g. -24dB to 0dB.
    # A simple linear multiplier is often best for percussion.
    out *= vel

    return out
