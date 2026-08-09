"""
NeuroDrums AI - Full Analysis Pipeline.

Multi-stage pipeline:
  Stage 1: Load & preprocess audio
  Stage 2: Drum separation (Demucs) or bypass if already a drum stem
  Stage 3: Onset detection (dual-method)
  Stage 4: Feature extraction per event
  Stage 5: AI classification (RF + ONNX)
  Stage 6: Roll detection & temporal post-processing

All stages run in a background thread.
Progress is reported via callback: progress_cb(stage_index, stage_name, fraction)
"""
from __future__ import annotations
import os
import sys
import time
import threading
import traceback
import numpy as np
from typing import List, Optional, Callable, Tuple

from core.models import DrumEvent, AudioInfo
from core.constants import LANE_NAMES
from ai.classifier import DrumClassifier
from ai.confidence import calibrate_confidence
from detection.onset import detect_onsets
from detection.transient import extract_features
from detection.beat import detect_bpm
from detection.roll import detect_rolls


STAGES = [
    "Loading audio",
    "Separating drums",
    "Detecting transients",
    "Extracting features",
    "Classifying drum events",
    "Post-processing & roll detection",
]


class AnalysisPipeline:
    """
    Orchestrates the full 6-stage drum analysis pipeline.
    """

    def __init__(self):
        self._classifier = DrumClassifier()
        self._thread: Optional[threading.Thread] = None
        self._cancelled = False

    def run_async(
        self,
        audio_path: str,
        sensitivity: str = "medium",
        use_gpu: bool = True,
        skip_separation: bool = False,
        progress_cb: Optional[Callable[[int, str, float], None]] = None,
        done_cb: Optional[Callable[[bool, str, List[DrumEvent], AudioInfo, float], None]] = None,
    ) -> None:
        """
        Run the pipeline in a background thread.

        Args:
            audio_path:       Path to source audio file
            sensitivity:      Detection sensitivity ('low','medium','high')
            use_gpu:          Whether to attempt GPU usage
            skip_separation:  If True, treat input as drum stem (skip Demucs)
            progress_cb:      Called with (stage_index, stage_name, fraction 0..1)
            done_cb:          Called with (success, error_msg, events, audio_info, bpm)
        """
        self._cancelled = False
        self._thread = threading.Thread(
            target=self._run,
            args=(audio_path, sensitivity, use_gpu, skip_separation, progress_cb, done_cb),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation of the running pipeline."""
        self._cancelled = True

    def _progress(self, cb, stage_idx, name, frac):
        if cb:
            try:
                cb(stage_idx, name, float(frac))
            except Exception:
                pass

    def _run(
        self,
        audio_path: str,
        sensitivity: str,
        use_gpu: bool,
        skip_separation: bool,
        progress_cb,
        done_cb,
    ):
        events: List[DrumEvent] = []
        audio_info = AudioInfo()
        bpm = 120.0

        try:
            # ──────────────────────────────────────────────────────
            # Stage 1: Load audio
            # ──────────────────────────────────────────────────────
            self._progress(progress_cb, 0, STAGES[0], 0.0)
            y, sr, audio_info = self._load_audio(audio_path)
            self._progress(progress_cb, 0, STAGES[0], 1.0)

            if self._cancelled:
                raise InterruptedError("Analysis cancelled.")

            # ──────────────────────────────────────────────────────
            # Stage 2: Separation
            # ──────────────────────────────────────────────────────
            self._progress(progress_cb, 1, STAGES[1], 0.0)
            drum_y, drum_sr = self._separate_or_bypass(
                y, sr, audio_path, use_gpu, skip_separation,
                lambda f: self._progress(progress_cb, 1, STAGES[1], f)
            )
            self._progress(progress_cb, 1, STAGES[1], 1.0)

            if self._cancelled:
                raise InterruptedError("Analysis cancelled.")

            # ──────────────────────────────────────────────────────
            # Stage 3: Onset detection
            # ──────────────────────────────────────────────────────
            self._progress(progress_cb, 2, STAGES[2], 0.0)
            onset_times, onset_strengths = detect_onsets(
                drum_y, drum_sr, sensitivity=sensitivity,
                progress_cb=lambda f: self._progress(progress_cb, 2, STAGES[2], f)
            )

            # Also detect BPM from the drum stem
            bpm = detect_bpm(drum_y, drum_sr)
            self._progress(progress_cb, 2, STAGES[2], 1.0)

            if self._cancelled:
                raise InterruptedError("Analysis cancelled.")

            # ──────────────────────────────────────────────────────
            # Stage 4: Feature extraction per event
            # ──────────────────────────────────────────────────────
            self._progress(progress_cb, 3, STAGES[3], 0.0)
            all_features = []
            n = max(1, len(onset_times))
            for i, (t, strength) in enumerate(zip(onset_times, onset_strengths)):
                if self._cancelled:
                    raise InterruptedError("Analysis cancelled.")
                feats = extract_features(drum_y, drum_sr, float(t))
                feats["onset_strength_peak"] = float(strength)
                all_features.append(feats)
                if i % max(1, n // 20) == 0:
                    self._progress(progress_cb, 3, STAGES[3], i / n)
            self._progress(progress_cb, 3, STAGES[3], 1.0)

            # ──────────────────────────────────────────────────────
            # Stage 5: Classification
            # ──────────────────────────────────────────────────────
            self._progress(progress_cb, 4, STAGES[4], 0.0)
            events = []
            n = max(1, len(onset_times))
            for i, (t, strength, feats) in enumerate(zip(onset_times, onset_strengths, all_features)):
                if self._cancelled:
                    raise InterruptedError("Analysis cancelled.")

                predicted, raw_confidence, probs = self._classifier.classify(feats)
                _, confidence, uncertain = calibrate_confidence(probs)

                # Compute end time from decay
                decay_t = feats.get("decay_time", 0.06)
                end_t = float(t) + min(decay_t + 0.02, 0.5)
                duration = end_t - float(t)

                ev = DrumEvent(
                    type=predicted,
                    start=float(t),
                    end=end_t,
                    duration=duration,
                    velocity=float(np.clip(feats.get("velocity", 0.5), 0, 1)),
                    confidence=confidence,
                    uncertain=uncertain,
                    spectral_centroid=feats.get("spectral_centroid", 0.0),
                    low_energy=feats.get("low_energy", 0.0),
                    mid_energy=feats.get("mid_energy", 0.0),
                    high_energy=feats.get("high_energy", 0.0),
                    zcr=feats.get("zcr", 0.0),
                    attack_time=feats.get("attack_time", 0.0),
                    onset_strength=float(strength),
                )
                events.append(ev)

                if i % max(1, n // 20) == 0:
                    self._progress(progress_cb, 4, STAGES[4], i / n)

            self._progress(progress_cb, 4, STAGES[4], 1.0)

            # ──────────────────────────────────────────────────────
            # Stage 6: Post-processing
            # ──────────────────────────────────────────────────────
            self._progress(progress_cb, 5, STAGES[5], 0.0)
            events = detect_rolls(events, drum_y, drum_sr)
            events.sort(key=lambda e: e.start)
            self._progress(progress_cb, 5, STAGES[5], 1.0)

            if done_cb:
                done_cb(True, "", events, audio_info, bpm)

        except InterruptedError as ie:
            if done_cb:
                done_cb(False, str(ie), events, audio_info, bpm)
        except Exception:
            tb = traceback.format_exc()
            print(f"[Pipeline] Error:\n{tb}")
            if done_cb:
                done_cb(False, tb.split('\n')[-2] if tb else "Unknown error", events, audio_info, bpm)

    def _load_audio(
        self, path: str
    ) -> Tuple[np.ndarray, int, AudioInfo]:
        """Load audio file, convert to mono float32."""
        import librosa
        import soundfile as sf

        info = AudioInfo(path=path, filename=os.path.basename(path))
        try:
            # Try soundfile first for lossless formats
            data, sr = sf.read(path, always_2d=True)
            info.sample_rate = sr
            info.channels = data.shape[1]
            info.format = path.split('.')[-1].upper()
            # Convert to mono
            if data.ndim == 2:
                y_mono = data.mean(axis=1).astype(np.float32)
            else:
                y_mono = data.astype(np.float32)
        except Exception:
            # Fallback to librosa (handles MP3 etc.)
            y_mono, sr = librosa.load(path, sr=None, mono=True)
            y_mono = y_mono.astype(np.float32)
            info.sample_rate = sr
            info.channels = 1
            info.format = path.split('.')[-1].upper()

        info.duration = len(y_mono) / sr
        return y_mono, sr, info

    def _separate_or_bypass(
        self,
        y: np.ndarray,
        sr: int,
        audio_path: str,
        use_gpu: bool,
        skip: bool,
        progress_cb,
    ) -> Tuple[np.ndarray, int]:
        """
        Either run Demucs separation or bypass if input is already a drum stem.
        """
        if skip:
            progress_cb(1.0)
            return y, sr

        # Detect if input is already a drum stem:
        # drum stems have very limited low-end outside kick range
        # and high percussive ratio. Heuristic: if percussive ratio > 0.75,
        # it's likely already a drum stem.
        if self._is_drum_stem(y, sr):
            print("[Pipeline] Input detected as drum stem — skipping Demucs separation.")
            progress_cb(1.0)
            return y, sr

        # Run Demucs
        return self._run_demucs(audio_path, sr, use_gpu, progress_cb)

    def _is_drum_stem(self, y: np.ndarray, sr: int) -> bool:
        """
        Heuristic check: is this audio likely already a drum stem?
        """
        try:
            import librosa
            # Short analysis window
            y_chunk = y[:min(sr * 5, len(y))]
            H, P = librosa.decompose.hpss(librosa.stft(y_chunk))
            perc_ratio = float(np.abs(P).mean() / (np.abs(H).mean() + np.abs(P).mean() + 1e-9))
            return perc_ratio > 0.72
        except Exception:
            return False

    def _run_demucs(
        self, audio_path: str, sr: int, use_gpu: bool, progress_cb
    ) -> Tuple[np.ndarray, int]:
        """Run Demucs htdemucs_ft for drum stem extraction."""
        import subprocess
        import soundfile as sf

        try:
            import torch
            device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

        out_dir = os.path.abspath("cache")
        os.makedirs(out_dir, exist_ok=True)

        progress_cb(0.05)

        cmd = [
            sys.executable, "-m", "demucs",
            "--two-stems=drums",
            "-n", "htdemucs_ft",
            "--shifts=2",
            "-d", device,
            "-o", out_dir,
            audio_path,
        ]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=flags,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Demucs failed: {result.stderr[-500:]}")

        name = os.path.splitext(os.path.basename(audio_path))[0]
        drum_path = os.path.join(out_dir, "htdemucs_ft", name, "drums.wav")

        if not os.path.exists(drum_path):
            raise FileNotFoundError(f"Demucs completed but drums.wav not found at: {drum_path}")

        progress_cb(0.9)

        data, new_sr = sf.read(drum_path, always_2d=True)
        y_drum = data.mean(axis=1).astype(np.float32)
        progress_cb(1.0)
        return y_drum, new_sr
