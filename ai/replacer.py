import numpy as np
import librosa
import soundfile as sf
import os
import warnings

# අනවශ්‍ය warnings අයින් කිරීම
warnings.filterwarnings('ignore', category=UserWarning)

class DrumReplacer:
    def __init__(self, sample_dir="samples"):
        self.sample_dir = sample_dir
        if not os.path.exists(self.sample_dir):
            os.makedirs(self.sample_dir)
        
        self.samples = {}
        # ඔයාගේ FL Studio Samples අකුරු හරියටම ගැලපෙන්න Load කිරීම
        self.load_sample("Kick", "Kick.wav")
        self.load_sample("Snare", "Snare.wav")
        self.load_sample("Hat", "Hat.wav")

    def load_sample(self, drum_type, filename):
        path = os.path.join(self.sample_dir, filename)
        if os.path.exists(path):
            try:
                # FL Studio WAVs වල ඇති ප්‍රශ්න මඟහරින්න librosa පාවිච්චි කිරීම
                y, sr = librosa.load(path, sr=None, mono=True)
                
                # Sample එක ලෝඩ් වුණත් සද්දෙ නැත්නම් (Silent නම්) බලනවා
                if np.max(np.abs(y)) == 0:
                    print(f"[Replacer] Warning: {filename} is completely silent!")
                else:
                    # Sample එකේ සද්දෙ උපරිම Quality එකට (Normalize) හදනවා
                    y = y / np.max(np.abs(y)) 
                    
                self.samples[drum_type] = (y, sr)
                print(f"[Replacer] Successfully Loaded {filename} for {drum_type}")
            except Exception as e:
                print(f"[Replacer] Error loading {filename}: {e}")
                self.samples[drum_type] = None
        else:
            print(f"[Replacer] Missing File: {filename} not found in {self.sample_dir}/")
            self.samples[drum_type] = None

    def replace(self, original_sr, classified_hits, output_length):
        replaced_y = np.zeros(output_length, dtype=np.float32)

        for hit in classified_hits:
            time = hit["time"]
            drum_type = hit["type"]
            
            if drum_type in self.samples and self.samples[drum_type] is not None:
                sample_y, sample_sr = self.samples[drum_type]
                
                if sample_sr != original_sr:
                    sample_y = librosa.resample(sample_y, orig_sr=sample_sr, target_sr=original_sr)
                
                start_sample = int(time * original_sr)
                end_sample = start_sample + len(sample_y)
                
                if end_sample <= len(replaced_y):
                    replaced_y[start_sample:end_sample] += sample_y
                else:
                    overlap = len(replaced_y) - start_sample
                    replaced_y[start_sample:] += sample_y[:overlap]
        
        # අන්තිමට හැදෙන මුළු ට්‍රැක් එකම Distortion නොවී උපරිම සද්දෙට (Normalize) හදනවා
        if np.max(np.abs(replaced_y)) > 0:
            replaced_y = replaced_y / np.max(np.abs(replaced_y))
            
        return replaced_y