from __future__ import annotations
import threading
import numpy as np


class AudioEngine:
    def __init__(self):
        self.original = None
        self.processed = None
        self.sr = 44100
        self.position = 0.0
        self.duration = 0.0
        self._stream = None
        self._playing = False
        self._paused = False
        self._lock = threading.RLock()
        self.loop_enabled = False
        self.loop_start = 0.0
        self.loop_end = 0.0

    def load(self, y, sr):
        self.stop()
        self.original = np.asarray(y, dtype=np.float32)
        self.processed = None
        self.sr = int(sr)
        self.duration = len(y) / sr
        self.position = 0.0
        self.loop_end = self.duration

    def set_processed(self, y):
        self.processed = np.asarray(y, dtype=np.float32)
        if self.processed.ndim == 1:
            self.processed = np.column_stack((self.processed, self.processed))

    @property
    def is_playing(self):
        return self._playing and not self._paused

    def _buffer(self):
        if self.processed is not None:
            return self.processed
        audio = self.original
        if audio is None:
            return None
        if audio.ndim == 1:
            return np.column_stack((audio, audio))
        return audio

    def play(self, start=None):
        audio = self._buffer()
        if audio is None:
            return
        if self._paused and self._stream is not None:
            self._paused = False
            self._playing = True
            try:
                self._stream.start()
            except Exception:
                self._paused = False
                self._playing = False
            return
        self.stop()
        if start is not None:
            self.position = max(0.0, min(float(start), self.duration))
        try:
            import sounddevice as sd

            with self._lock:
                self._playing = True
                self._paused = False

            channels = 2 if audio.ndim == 2 else 1

            def callback(outdata, frames, time_info, status):
                with self._lock:
                    if not self._playing or self._paused:
                        outdata.fill(0)
                        if not self._playing:
                            raise sd.CallbackStop()
                        return
                    i = int(self.position * self.sr)
                    chunk = audio[i : i + frames]
                    if chunk.ndim == 1:
                        chunk = chunk[:, None]
                    n = len(chunk)
                    outdata.fill(0)
                    ch = min(outdata.shape[1], chunk.shape[1] if chunk.ndim == 2 else 1)
                    if n:
                        if chunk.ndim == 1:
                            outdata[:n, :ch] = chunk[:n, None]
                        else:
                            outdata[:n, :ch] = chunk[:n, :ch]
                    self.position += frames / self.sr
                    if self.loop_enabled and self.position >= self.loop_end:
                        self.position = self.loop_start
                    elif self.position >= self.duration:
                        if self.loop_enabled:
                            self.position = self.loop_start
                        else:
                            self._playing = False
                            raise sd.CallbackStop()

            self._stream = sd.OutputStream(
                samplerate=self.sr,
                channels=channels,
                dtype='float32',
                callback=callback,
                blocksize=1024,
            )
            self._stream.start()
        except Exception:
            self._playing = False
            self._paused = False
            raise

    def pause(self):
        with self._lock:
            if self._playing and not self._paused:
                self._paused = True
                if self._stream:
                    try:
                        self._stream.stop()
                    except Exception:
                        pass

    def stop(self):
        with self._lock:
            self._playing = False
            self._paused = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def seek(self, seconds):
        self.position = max(0.0, min(float(seconds), self.duration))

    def set_loop(self, enabled: bool, start: float = 0.0, end: float | None = None):
        self.loop_enabled = enabled
        self.loop_start = max(0.0, start)
        self.loop_end = end if end is not None else self.duration
