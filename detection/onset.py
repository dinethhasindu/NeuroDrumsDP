from __future__ import annotations
import numpy as np

def detect_onsets(y, sr, sensitivity='medium'):
    import librosa
    delta={'low':0.32,'medium':0.20,'high':0.10}.get(sensitivity,0.20)
    wait={'low':7,'medium':3,'high':1}.get(sensitivity,3)
    hop=256
    env=librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, aggregate=np.median)
    if len(env)==0: return np.empty(0), np.empty(0)
    frames=librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, backtrack=True,
        pre_max=8, post_max=8, pre_avg=16, post_avg=16, delta=delta, wait=wait)
    times=librosa.frames_to_time(frames,sr=sr,hop_length=hop)
    strengths=env[np.clip(frames,0,len(env)-1)]
    strengths=strengths/(np.max(env)+1e-9)
    return times.astype(float), strengths.astype(float)

def detect_bpm(y,sr):
    try:
        import librosa
        tempo,_=librosa.beat.beat_track(y=y,sr=sr)
        return float(np.asarray(tempo).reshape(-1)[0]) if np.size(tempo) else 120.0
    except Exception: return 120.0
