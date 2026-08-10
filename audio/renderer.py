from __future__ import annotations
import os
import numpy as np
from core.constants import LANE_NAMES
from audio.loader import load_audio
from replacement.envelope import apply_envelope
from replacement.pitch import apply_pitch_and_speed
from replacement.velocity import apply_velocity
from replacement.alignment import align_transient
from replacement.masking import apply_mask


def _to_stereo(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        return np.column_stack((y, y))
    if y.shape[1] == 1:
        return np.column_stack((y[:, 0], y[:, 0]))
    return y[:, :2].astype(np.float32)


def _pan_gains(pan: float) -> tuple[float, float]:
    pan = max(-1.0, min(1.0, float(pan)))
    angle = (pan + 1.0) * np.pi / 4.0
    return float(np.cos(angle)), float(np.sin(angle))


def _apply_fades(sample: np.ndarray, sr: int, fade_in_ms: float, fade_out_ms: float) -> np.ndarray:
    out = sample.copy()
    n = len(out)
    if fade_in_ms > 0:
        fi = min(n, max(1, int(fade_in_ms / 1000.0 * sr)))
        out[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
    if fade_out_ms > 0:
        fo = min(n, max(1, int(fade_out_ms / 1000.0 * sr)))
        out[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    return out


class AudioRenderer:
    """Single authoritative render path for preview hit, playback, and export."""

    def __init__(self, sr: int):
        self.sr = int(sr)
        self._sample_cache: dict[str, np.ndarray] = {}

    def _load_sample(self, path: str) -> np.ndarray | None:
        if not path or not os.path.isfile(path):
            return None
        if path not in self._sample_cache:
            try:
                y, _, _ = load_audio(path, target_sr=self.sr, mono=True)
                self._sample_cache[path] = y
            except Exception:
                return None
        return self._sample_cache[path]

    def _lane_active(self, ev, lanes) -> bool:
        if ev.muted or ev.removed:
            return False
        solo = {n for n, s in lanes.items() if s.soloed}
        if solo and ev.type not in solo:
            return False
        if ev.type in lanes and lanes[ev.type].muted:
            return False
        return True

    def _process_buffer(self, ev, audio: np.ndarray) -> np.ndarray:
        out = apply_pitch_and_speed(audio, self.sr, ev.pitch, ev.speed)
        out = apply_envelope(out, self.sr, ev.decay_ms, ev.fade_in_ms, ev.fade_out_ms, ev.punch)
        out = apply_velocity(
            out, ev.velocity, ev.match_velocity, ev.velocity_curve, ev.volume_db
        )
        lane_vol = 1.0
        return out * lane_vol

    def _extract_original_slice(self, original: np.ndarray, ev) -> np.ndarray:
        src_start = int(max(0, (ev.start + ev.source_offset_ms / 1000.0) * self.sr))
        n = max(1, int(ev.duration * self.sr))
        src_end = min(len(original), src_start + n)
        chunk = original[src_start:src_end].astype(np.float32)
        if len(chunk) < n:
            chunk = np.pad(chunk, (0, n - len(chunk)))
        return chunk

    def render_event(self, ev, original_mono: np.ndarray, lanes) -> tuple[np.ndarray, int, int] | None:
        if not self._lane_active(ev, lanes):
            return None

        pos = int(max(0, (ev.start + ev.timing_offset_ms / 1000.0) * self.sr))

        if ev.replacement_sample and os.path.isfile(ev.replacement_sample):
            sample = self._load_sample(ev.replacement_sample)
            if sample is None:
                return None
            src_off = int(max(0, ev.source_offset_ms / 1000.0 * self.sr))
            n = max(1, int(ev.duration * self.sr))
            chunk = sample[src_off:src_off + n]
            if len(chunk) < n:
                chunk = np.pad(chunk, (0, n - len(chunk)))
            processed = self._process_buffer(ev, chunk)
            orig_seg = self._extract_original_slice(original_mono, ev)
            if len(orig_seg) >= 64 and ev.replace_mode in ('replace', 'layer'):
                processed = align_transient(orig_seg[: len(processed)], processed)
        else:
            chunk = self._extract_original_slice(original_mono, ev)
            processed = self._process_buffer(ev, chunk)

        lg, rg = _pan_gains(ev.pan)
        stereo = np.column_stack((processed * lg, processed * rg)).astype(np.float32)
        end = pos + len(stereo)
        return stereo, pos, end

    def render(
        self,
        original,
        events,
        lanes,
        *,
        solo_original: bool = False,
    ):
        mono = original[:, 0] if getattr(original, 'ndim', 1) == 2 else np.asarray(original, dtype=np.float32)
        out = _to_stereo(original)

        solo = {n for n, s in lanes.items() if s.soloed}
        if solo:
            out *= 0.0

        # Build mute/replace masks on original
        replace_regions: list[tuple[int, int, float]] = []
        mute_regions: list[tuple[int, int]] = []

        sorted_events = sorted(
            [e for e in events if not e.removed],
            key=lambda e: e.start,
        )

        for ev in sorted_events:
            if ev.muted:
                a = int(max(0, ev.start * self.sr))
                b = int(min(len(mono), (ev.end + 0.005) * self.sr))
                if b > a:
                    mute_regions.append((a, b))
                continue
            if ev.replacement_sample and os.path.isfile(ev.replacement_sample) and ev.replace_mode == 'replace':
                a = int(max(0, (ev.start + ev.timing_offset_ms / 1000.0) * self.sr))
                b = int(min(len(mono), a + max(1, int(ev.duration * self.sr))))
                att = getattr(ev, 'original_attenuation', 1.0)
                replace_regions.append((a, b, att))

        masked = mono.copy()
        for a, b in mute_regions:
            masked[a:b] = 0.0
        for a, b, att in replace_regions:
            seg_len = b - a
            if seg_len > 0:
                seg = masked[a:b]
                masked[a:b] = apply_mask(seg, 0, seg_len, att)[:seg_len]

        out[:, 0] = masked
        out[:, 1] = masked

        if solo and not any(not e.muted and not e.removed for e in sorted_events if e.type in solo):
            pass
        elif solo_original and not solo:
            pass

        for ev in sorted_events:
            rendered = self.render_event(ev, mono, lanes)
            if rendered is None:
                continue
            stereo, pos, end = rendered
            end = min(len(out), end)
            if end <= pos:
                continue
            n = end - pos
            if ev.replace_mode == 'replace' and ev.replacement_sample:
                att = getattr(ev, 'original_attenuation', 1.0)
                out[pos:end] *= max(0.0, 1.0 - att)
            out[pos:end] += stereo[:n]

        return np.clip(out, -1.0, 1.0), self.sr

    def render_single_hit(self, ev, original_mono: np.ndarray | None, lanes, min_duration: float = 2.0):
        """Preview a single event in isolation."""
        silence_len = int(self.sr * max(min_duration, ev.duration + 0.5))
        if original_mono is None:
            original_mono = np.zeros(silence_len, dtype=np.float32)
        ev_copy = ev
        pos = int(max(0, ev.timing_offset_ms / 1000.0 * self.sr))
        rendered = self.render_event(ev_copy, original_mono, lanes)
        out = np.zeros((silence_len, 2), dtype=np.float32)
        if rendered:
            stereo, _, end = rendered
            end = min(silence_len, pos + len(stereo))
            if end > pos:
                out[pos:end] += stereo[: end - pos]
        return np.clip(out, -1.0, 1.0), self.sr
