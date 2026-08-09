import threading, time
import numpy as np
import soundfile as sf
import sounddevice as sd

class AudioPlayer:
    def __init__(self):
        self.audio = None
        self.sr = None
        self.started_at = 0.0
        self.offset = 0.0
        self.playing = False

    def load(self, y, sr):
        self.audio = np.asarray(y, dtype=np.float32)
        self.sr = sr
        self.stop()

    def play(self, start=0.0):
        if self.audio is None: return
        self.stop()
        start = float(np.clip(start, 0, len(self.audio)/self.sr))
        self.offset = start
        self.started_at = time.perf_counter()
        self.playing = True
        threading.Thread(target=self._play_thread, args=(start,), daemon=True).start()

    def _play_thread(self, start):
        idx = int(start*self.sr)
        try:
            sd.play(self.audio[idx:], self.sr, blocking=True)
        finally:
            self.playing = False

    def position(self):
        if not self.playing:
            return self.offset
        return self.offset + (time.perf_counter()-self.started_at)

    def stop(self):
        sd.stop()
        if self.playing:
            self.offset = self.position()
        self.playing = False
