"""
NeuroDrums AI - Audio Playback Engine.

Real-time audio playback with:
  - Callback-driven position updates for smooth playhead
  - Support for playing original OR mixed/processed audio
  - Low-latency sounddevice OutputStream
  - Thread-safe play/stop/seek
"""
from __future__ import annotations
import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
from typing import Optional, Callable


class AudioEngine:
    """
    Manages real-time audio playback.

    Two audio buffers:
      original:   unmodified loaded audio
      processed:  rendered mix with replacements applied

    The user can switch between them at any time.
    """

    def __init__(self):
        self.original: Optional[np.ndarray] = None
        self.processed: Optional[np.ndarray] = None
        self.sr: int = 44100
        self.duration: float = 0.0
        self.position: float = 0.0

        self._stream: Optional[sd.OutputStream] = None
        self._playing: bool = False
        self._lock = threading.RLock()
        self._preview_mode: str = "original"  # "original" or "processed"

    # ── Loading ─────────────────────────────────────────────────────────
    def load(self, y: np.ndarray, sr: int) -> None:
        """
        Load audio into the engine.
        """
        self.stop()
        self.original = y.astype(np.float32)
        self.sr = sr
        self.duration = len(y) / sr
        self.position = 0.0
        self.processed = None

    def set_processed(self, y: np.ndarray) -> None:
        """Update the processed/mixed audio buffer."""
        self.processed = y.astype(np.float32)

    def set_preview_mode(self, mode: str) -> None:
        """Switch between 'original' and 'processed' playback."""
        assert mode in ("original", "processed")
        self._preview_mode = mode

    # ── Playback ─────────────────────────────────────────────────────────
    def play(
        self,
        start: Optional[float] = None,
        on_position: Optional[Callable[[float], None]] = None,
    ) -> None:
        """
        Start playback from current position (or given start time).

        Args:
            start:       start time in seconds (optional)
            on_position: callback called every audio block with current time
        """
        audio = self._get_playback_buffer()
        if audio is None:
            return

        # Stop any active stream before taking the state lock.  Calling
        # ``stop`` while holding a non-reentrant lock used to deadlock every
        # call to ``play``.
        self.stop()
        with self._lock:
            if start is not None:
                self.position = float(max(0.0, min(start, self.duration)))
            self._playing = True

        def callback(outdata, frames, time_info, status):
            with self._lock:
                if not self._playing:
                    outdata.fill(0)
                    raise sd.CallbackStop()

                i = int(self.position * self.sr)
                chunk = audio[i: i + frames]
                n = len(chunk)

                if n == 0:
                    outdata.fill(0)
                    self._playing = False
                    raise sd.CallbackStop()

                if chunk.ndim == 2:
                    chunk_mono = chunk.mean(axis=1)
                else:
                    chunk_mono = chunk

                if outdata.shape[1] == 1:
                    outdata[:n, 0] = chunk_mono
                    if n < frames:
                        outdata[n:, 0] = 0
                else:
                    if chunk.ndim == 2 and chunk.shape[1] >= 2:
                        outdata[:n, :2] = chunk[:, :2]
                    else:
                        outdata[:n, 0] = chunk_mono
                        outdata[:n, 1] = chunk_mono
                    if n < frames:
                        outdata[n:] = 0

                self.position += frames / self.sr
                if self.position >= self.duration:
                    self._playing = False
                    raise sd.CallbackStop()

            if on_position:
                on_position(self.position)

        try:
            channels = sd.default.channels or 1
            if isinstance(channels, (list, tuple)):
                channels = channels[1] or 1
            channels = max(1, min(2, channels))
        except Exception:
            channels = 1

        stream = sd.OutputStream(
            samplerate=self.sr,
            channels=channels,
            dtype='float32',
            callback=callback,
            blocksize=1024,
        )
        self._stream = stream
        stream.start()

    def stop(self) -> None:
        """Stop playback."""
        with self._lock:
            self._playing = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def seek(self, time: float) -> None:
        """Seek to time position without stopping."""
        with self._lock:
            self.position = float(max(0.0, min(time, self.duration)))

    @property
    def is_playing(self) -> bool:
        return self._playing

    def _get_playback_buffer(self) -> Optional[np.ndarray]:
        if self._preview_mode == "processed" and self.processed is not None:
            return self.processed
        return self.original

    # ── Export ───────────────────────────────────────────────────────────
    def export_wav(self, path: str, y: Optional[np.ndarray] = None, bit_depth: int = 24) -> None:
        """Export audio to WAV file."""
        audio = y if y is not None else self.processed
        if audio is None:
            audio = self.original
        if audio is None:
            raise ValueError("No audio to export")
        subtype = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}.get(bit_depth, "PCM_24")
        sf.write(path, audio, self.sr, subtype=subtype)
