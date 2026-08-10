from __future__ import annotations
import threading
import numpy as np

class AudioEngine:
    def __init__(self):
        self.original = None; self.processed = None; self.sr = 44100; self.position = 0.0; self.duration = 0.0
        self._stream = None; self._playing = False; self._lock = threading.RLock(); self.preview_mode = 'original'
    def load(self, y, sr):
        self.stop(); self.original = np.asarray(y, dtype=np.float32); self.processed = None; self.sr=int(sr); self.duration=len(y)/sr; self.position=0.0
    def set_processed(self, y): self.processed=np.asarray(y,dtype=np.float32)
    @property
    def is_playing(self): return self._playing
    def _buffer(self): return self.processed if self.preview_mode=='processed' and self.processed is not None else self.original
    def play(self, start=None):
        audio=self._buffer()
        if audio is None: return
        self.stop()
        if start is not None: self.position=max(0.0,min(float(start),self.duration))
        try:
            import sounddevice as sd
            with self._lock: self._playing=True
            def callback(outdata, frames, time_info, status):
                with self._lock:
                    if not self._playing: outdata.fill(0); raise sd.CallbackStop()
                    i=int(self.position*self.sr); chunk=audio[i:i+frames]
                    if chunk.ndim==1: chunk=chunk[:,None]
                    n=len(chunk)
                    outdata.fill(0)
                    if n: outdata[:n,:min(outdata.shape[1],chunk.shape[1])] = chunk[:n,:min(outdata.shape[1],chunk.shape[1])]
                    self.position += frames/self.sr
                    if self.position >= self.duration: self._playing=False; raise sd.CallbackStop()
            self._stream=sd.OutputStream(samplerate=self.sr, channels=1 if audio.ndim==1 else min(2,audio.shape[1]), dtype='float32', callback=callback, blocksize=1024)
            self._stream.start()
        except Exception:
            self._playing=False
            raise
    def stop(self):
        with self._lock: self._playing=False
        if self._stream:
            try: self._stream.stop(); self._stream.close()
            except Exception: pass
            self._stream=None
    def seek(self, seconds): self.position=max(0.0,min(float(seconds),self.duration))
