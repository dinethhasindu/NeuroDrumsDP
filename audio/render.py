import numpy as np, librosa
from scipy.signal import resample

def transform(sample,sr,volume=1,pitch=0,punch=.65,decay=450,speed=1):
    x=np.asarray(sample,dtype=np.float32)
    if len(x)==0:return x
    if pitch:
        x=librosa.effects.pitch_shift(x,sr=sr,n_steps=float(pitch))
    if speed!=1:
        n=max(16,int(len(x)/max(.1,float(speed))))
        x=resample(x,n).astype(np.float32)
    # punch: emphasize transient
    if punch!=.65:
        d=np.diff(np.r_[0,x])
        x=x*(1-punch*.35)+d*punch*.15
    n=max(8,int(sr*decay/1000))
    if n<len(x):
        env=np.ones(len(x),dtype=np.float32)
        env[-n:]=np.linspace(1,0,n)
        x*=env
    return x*float(volume)

def render_track(original,sr,events,samples,mutes=None):
    y=original.copy().astype(np.float32)
    mutes=mutes or set()
    for e in events:
        typ=e["type"]
        if typ in mutes: continue
        s=samples.get(typ)
        if s is None: continue
        t=e["time"]; center=int(t*sr)
        radius=max(64,int(.015*sr))
        a=max(0,center-radius); b=min(len(y),center+radius)
        y[a:b]*=0.12
        z=transform(s,sr,e.get("volume",1),e.get("pitch",0),e.get("punch",.65),e.get("decay",450),e.get("speed",1))
        end=min(len(y),a+len(z))
        if end>a:y[a:end]+=z[:end-a]*e.get("strength",1)
    return np.clip(y,-1,1)
