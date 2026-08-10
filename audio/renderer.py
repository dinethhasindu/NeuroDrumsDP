from __future__ import annotations
import os
import numpy as np
from core.constants import LANE_NAMES
from audio.loader import load_audio

class AudioRenderer:
    def __init__(self, sr): self.sr=sr
    def render(self, original, events, lanes):
        out=np.asarray(original,dtype=np.float32).copy()
        solo={n for n,s in lanes.items() if s.soloed}
        for ev in events:
            if ev.removed or ev.muted or not ev.replacement_sample or not os.path.isfile(ev.replacement_sample): continue
            if solo and ev.type not in solo: continue
            try: sample, sr, _=load_audio(ev.replacement_sample, target_sr=self.sr, mono=True)
            except Exception: continue
            if ev.speed != 1.0:
                import librosa
                sample=librosa.effects.time_stretch(sample, rate=max(0.25,min(4.0,ev.speed)))
            if ev.pitch:
                import librosa
                sample=librosa.effects.pitch_shift(sample, sr=self.sr, n_steps=ev.pitch)
            if ev.decay_ms>0:
                length=max(1,int(ev.decay_ms/1000*self.sr)); sample=sample[:length]
            if ev.fade_in_ms>0:
                n=min(len(sample),max(1,int(ev.fade_in_ms/1000*self.sr))); sample[:n]*=np.linspace(0,1,n)
            if ev.fade_out_ms>0:
                n=min(len(sample),max(1,int(ev.fade_out_ms/1000*self.sr))); sample[-n:]*=np.linspace(1,0,n)
            gain=10**(ev.volume_db/20.0) * max(0.0,min(1.5,ev.velocity if ev.match_velocity else 1.0))
            sample=sample*gain
            pos=int(max(0,ev.start+ev.timing_offset_ms/1000)*self.sr)
            end=min(len(out),pos+len(sample))
            if end<=pos: continue
            if ev.replace_mode=='replace':
                out[pos:end] *= max(0.0,1.0-ev.original_attenuation)
            out[pos:end] += sample[:end-pos]
        return np.clip(out,-1,1), self.sr
