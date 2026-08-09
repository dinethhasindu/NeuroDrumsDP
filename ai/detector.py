import librosa
import numpy as np

class DrumDetector:
    def __init__(self):
        pass

    def detect_and_classify(self, y, sr):
        try:
            # 1. මුලින්ම Hits තියෙන තැන්වල Time එක හොයාගන්නවා
            onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time', backtrack=True)
            onset_frames = librosa.time_to_frames(onsets, sr=sr)
            
            classified_hits = []
            
            # 2. හැම Hit එකක්ම එකින් එක අරගෙන ඒකේ සද්දෙ මොකක්ද කියලා බලනවා
            for idx, frame in enumerate(onset_frames):
                time = onsets[idx]
                
                # Hit එකක් පටන් ගන්න තැන ඉඳන් මිලි තත්පර 50ක (0.05s) පොඩි කෑල්ලක් කපාගන්නවා
                start_sample = int(time * sr)
                end_sample = min(len(y), int((time + 0.05) * sr))
                hit_audio = y[start_sample:end_sample]
                
                if len(hit_audio) == 0:
                    continue
                    
                # සද්දේ Frequency එක (Spectral Centroid) මනිනවා
                centroid = librosa.feature.spectral_centroid(y=hit_audio, sr=sr)[0]
                mean_centroid = np.mean(centroid)
                
                # Frequency එක අනුව වර්ග කරනවා
                if mean_centroid < 1500:
                    hit_type = "Kick"
                elif 1500 <= mean_centroid < 4000:
                    hit_type = "Snare"
                else:
                    hit_type = "Hat"
                    
                # Time එකයි, වර්ගයයි ලිස්ට් එකට දානවා
                classified_hits.append({"time": time, "type": hit_type})
            
            return classified_hits
            
        except Exception as e:
            print(f"[DrumDetector] Error: {e}")
            return []