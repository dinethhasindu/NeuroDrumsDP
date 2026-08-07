import soundfile as sf
import sounddevice as sd
import numpy as np

class AudioPlayer:
    def __init__(self):
        self.y_raw = None
        self.sr = None

    def load_file(self, file_path):
        try:
            # Read audio file
            self.y_raw, self.sr = sf.read(file_path)
            
            # Convert to mono just for the waveform visualizer
            if len(self.y_raw.shape) > 1:
                y_mono = np.mean(self.y_raw, axis=1)
            else:
                y_mono = self.y_raw
                
            return y_mono, self.sr
            
        except Exception as e:
            print(f"[Audio Engine] Error loading file: {e}")
            return None, None

    def play(self):
        if self.y_raw is not None:
            # Non-blocking playback
            sd.play(self.y_raw, self.sr)

    def stop(self):
        sd.stop()