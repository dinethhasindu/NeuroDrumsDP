"""
NeuroDrums AI - Replacement Engine.

Core engine for processing a drum event and generating the replacement audio.
Ties together alignment, envelope, pitch, velocity, and masking.
"""
from __future__ import annotations
import os
import numpy as np
from typing import Optional, Tuple

from core.models import DrumEvent
from replacement.alignment import align_transient
from replacement.velocity import apply_velocity
from replacement.envelope import apply_envelope
from replacement.pitch import apply_pitch_and_speed
from replacement.masking import apply_mask
from audio.loader import load_audio

class ReplacementEngine:
    """
    Renders replacement audio for drum events.
    Caches loaded samples in memory to avoid disk reads during playback.
    """
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        self._sample_cache = {}  # path -> audio array

    def _get_sample(self, path: str) -> Optional[np.ndarray]:
        if not path or not os.path.exists(path):
            return None
        if path not in self._sample_cache:
            try:
                y, _, _ = load_audio(path, target_sr=self.sr, mono=True)
                self._sample_cache[path] = y
            except Exception as e:
                print(f"[Engine] Failed to load sample {path}: {e}")
                return None
        return self._sample_cache[path]

    def render_event(
        self,
        event: DrumEvent,
        original_audio: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], int, int]:
        """
        Renders the replacement audio for a single event.

        Returns:
            (replacement_audio, masked_original_audio, start_sample, end_sample)
        """
        if (
            event.muted
            or event.removed
            or event.replace_mode == "original"
            or not event.replacement_sample
        ):
            return None, None, 0, 0

        sample_audio = self._get_sample(event.replacement_sample)
        if sample_audio is None:
            return None, None, 0, 0

        # Start and end samples in the full track
        start_sample = int((event.start + (event.timing_offset_ms / 1000.0)) * self.sr)
        start_sample = max(0, start_sample)
        
        # 1. Pitch & Speed
        processed = apply_pitch_and_speed(
            sample_audio, self.sr, event.pitch, event.speed
        )

        # 2. Envelope & Decay
        processed = apply_envelope(
            processed, self.sr, event.decay_ms, event.fade_in_ms, event.fade_out_ms, event.punch
        )

        # 3. Velocity & Volume
        processed = apply_velocity(
            processed, event.velocity, event.match_velocity, event.velocity_curve, event.volume_db
        )

        end_sample = start_sample + len(processed)
        
        # 4. Alignment
        # Extract the segment from the original audio for alignment
        if event.replace_mode in ("replace", "layer") and end_sample <= len(original_audio):
            orig_segment = original_audio[start_sample:end_sample]
            processed = align_transient(orig_segment, processed)
            
        # Re-calculate end sample after alignment in case length changed
        end_sample = start_sample + len(processed)

        # 5. Masking
        masked_orig = None
        if event.replace_mode == "replace":
            # Duck the original audio
            if end_sample <= len(original_audio):
                orig_segment = original_audio[start_sample:end_sample]
                masked_orig = apply_mask(
                    orig_segment, 0, len(orig_segment), event.original_attenuation
                )
        
        # Panning (if stereo, but we return mono and mixer handles panning, or we return stereo here)
        # For simplicity, returning mono. Mixer will handle panning when compositing.

        return processed, masked_orig, start_sample, end_sample
