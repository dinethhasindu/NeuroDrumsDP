"""
NeuroDrums AI - Audio Mixer & Renderer.

Takes the original audio, a list of events, and lane states,
and produces the final rendered audio mix and individual stems.
"""
from __future__ import annotations
import numpy as np
from typing import List, Dict, Tuple

from core.models import DrumEvent, LaneState
from replacement.engine import ReplacementEngine
from core.constants import LANE_NAMES

class AudioRenderer:
    """
    Renders the full project mix by processing all events through the ReplacementEngine
    and mixing them with the original audio.
    """
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        self.engine = ReplacementEngine(sample_rate)

    def render(
        self,
        original_audio: np.ndarray,
        events: List[DrumEvent],
        lane_states: Dict[str, LaneState],
        progress_cb=None,
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Renders the full mix and individual stems.
        
        Args:
            original_audio: The mono original drum stem.
            events: List of all DrumEvents.
            lane_states: Dict of LaneStates for muting/soloing/volume.
            
        Returns:
            (full_mix_stereo, {lane_name: stem_stereo})
        """
        n_samples = len(original_audio)
        
        # We process in stereo.
        mix_l = original_audio.copy()
        mix_r = original_audio.copy()
        
        # Initialize stems
        stems: Dict[str, Tuple[np.ndarray, np.ndarray]] = {
            lane: (np.zeros(n_samples, dtype=np.float32), np.zeros(n_samples, dtype=np.float32))
            for lane in LANE_NAMES
        }
        
        # Original stem gets a separate lane for mixdown if we want
        stems["Original"] = (original_audio.copy(), original_audio.copy())
        
        # Apply mute/solo logic
        is_any_solo = any(s.soloed for s in lane_states.values())
        
        for i, event in enumerate(events):
            if progress_cb and i % max(1, len(events)//20) == 0:
                progress_cb(i / max(1, len(events)))

            lane_state = lane_states.get(event.type)
            if not lane_state:
                continue
                
            # Skip if muted or not soloed when others are
            if lane_state.muted or (is_any_solo and not lane_state.soloed):
                continue
                
            # Render event
            repl_audio, masked_orig, start, end = self.engine.render_event(event, original_audio)
            
            if repl_audio is None:
                continue
                
            end = min(end, n_samples)
            if start >= end:
                continue
                
            repl_len = end - start
            repl_audio = repl_audio[:repl_len]
            
            # Panning
            pan = event.pan
            gain_l = np.sqrt(0.5 * (1.0 - pan))
            gain_r = np.sqrt(0.5 * (1.0 + pan))
            
            # Apply lane volume
            lane_vol = lane_state.volume
            
            repl_l = repl_audio * gain_l * lane_vol
            repl_r = repl_audio * gain_r * lane_vol
            
            # Add to stem
            stems[event.type][0][start:end] += repl_l
            stems[event.type][1][start:end] += repl_r
            
            # Masking original (in the main mix and Original stem)
            if masked_orig is not None:
                masked_orig = masked_orig[:repl_len]
                # the mask replaces the original audio in that segment
                # since we copied the original, we just overwrite it
                mix_l[start:end] = masked_orig
                mix_r[start:end] = masked_orig
                stems["Original"][0][start:end] = masked_orig
                stems["Original"][1][start:end] = masked_orig
                
        # Combine stems into mix
        for lane in LANE_NAMES:
            lane_state = lane_states.get(lane)
            if not lane_state or lane_state.muted or (is_any_solo and not lane_state.soloed):
                continue
            mix_l += stems[lane][0]
            mix_r += stems[lane][1]
            
        # Format stems to 2D arrays (samples, channels)
        out_stems = {}
        for lane, (l, r) in stems.items():
            out_stems[lane] = np.stack([l, r], axis=-1)
            
        full_mix = np.stack([mix_l, mix_r], axis=-1)
        
        # Hard clipper to prevent distortion
        full_mix = np.clip(full_mix, -1.0, 1.0)
        for lane in out_stems:
            out_stems[lane] = np.clip(out_stems[lane], -1.0, 1.0)
            
        if progress_cb:
            progress_cb(1.0)
            
        return full_mix, out_stems
