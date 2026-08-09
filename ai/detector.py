import numpy as np, librosa

LANES=["Kick","Snare","Closed Hat","Open Hat","Clap","Roll","Snare Roll","FX"]

class DrumDetector:
    def __init__(self, model_path=None):
        self.model_path=model_path
        self.ort=None
        if model_path:
            try:
                import onnxruntime as ort
                self.ort=ort
            except Exception:
                self.ort=None

    def detect(self,y,sr):
        # Stable local fallback: onset candidates + multi-band descriptors.
        onset_env=librosa.onset.onset_strength(y=y,sr=sr,hop_length=256)
        frames=librosa.onset.onset_detect(onset_envelope=onset_env,sr=sr,hop_length=256,
                                          backtrack=True,pre_max=8,post_max=8,
                                          pre_avg=16,post_avg=16,delta=0.18,wait=2)
        times=librosa.frames_to_time(frames,sr=sr,hop_length=256)
        out=[]
        for t in times:
            a=max(0,int((t-0.008)*sr)); b=min(len(y),int((t+0.16)*sr))
            x=y[a:b]
            if len(x)<128: continue
            rms=float(np.sqrt(np.mean(x*x))+1e-9)
            spec=np.abs(librosa.stft(x,n_fft=1024,hop_length=256))
            freqs=librosa.fft_frequencies(sr=sr,n_fft=1024)
            e=np.mean(spec,axis=1)
            low=e[(freqs<180)].sum(); mid=e[(freqs>=180)&(freqs<2500)].sum()
            high=e[freqs>=2500].sum(); total=low+mid+high+1e-9
            centroid=float(librosa.feature.spectral_centroid(S=spec,sr=sr).mean())
            zcr=float(librosa.feature.zero_crossing_rate(x).mean())
            duration=len(x)/sr
            lowp,midp,highp=low/total,mid/total,high/total
            if lowp>0.48 and centroid<900:
                typ="Kick"
            elif highp>0.60 and centroid>5500:
                # longer high-frequency hit -> open hat / crash-like FX
                typ="Open Hat" if duration>0.055 else "Closed Hat"
            elif midp>0.40 and highp>0.20 and zcr>0.08:
                typ="Snare"
            elif midp>0.48 and highp>0.30:
                typ="Clap"
            elif highp>0.45:
                typ="Closed Hat"
            else:
                typ="FX"
            out.append({"time":float(t),"type":typ,"strength":min(1.5,rms*20),
                        "confidence":0.45,"selected":False})
        # Convert dense repeated hits into roll labels conservatively.
        for i,e in enumerate(out):
            near=sum(1 for j in range(max(0,i-4),min(len(out),i+5))
                     if j!=i and 0<out[j]["time"]-e["time"]<0.14)
            if near>=2 and e["type"]=="Snare":
                e["type"]="Snare Roll"
            elif near>=3 and e["type"] in ("Closed Hat","Snare"):
                e["type"]="Roll"
        return out
