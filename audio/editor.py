import numpy as np
import librosa
import soundfile as sf

def load_audio(path, sr=None):
    y, rate = librosa.load(path, sr=sr, mono=True)
    return y.astype(np.float32), rate

def sample_transform(path, target_sr, volume=1.0, pitch=0.0, speed=1.0,
                     decay_ms=450, punch=0.65):
    y, sr = load_audio(path, target_sr)
    if len(y) == 0: return y
    # pitch first, then speed. librosa pitch shift preserves duration.
    if abs(pitch) > 1e-3:
        y = librosa.effects.pitch_shift(y, sr=sr, n_steps=float(pitch))
    if abs(speed-1.0) > 1e-3:
        y = librosa.effects.time_stretch(y, rate=max(0.05,float(speed)))
    # punch: transient emphasis using a short high-passed difference.
    if punch != 0.65 and len(y) > 16:
        hp = y - np.convolve(y, np.ones(9)/9, mode="same")
        y = y + (float(punch)-0.65)*1.25*hp
    # decay = fade-out target.
    if decay_ms > 0:
        n = min(len(y), int(target_sr*decay_ms/1000))
        if n > 8:
            fade = np.linspace(1, 0, n, dtype=np.float32)
            y[-n:] *= fade
    y *= float(volume)
    return np.clip(y, -1, 1).astype(np.float32)

def render_replacements(original, sr, events, lane_samples, lane_settings,
                        mute_types=None):
    out = np.array(original, dtype=np.float32, copy=True)
    mute_types = set(mute_types or [])
    # Remove each detected hit with a short local fade, then overlay replacement.
    for ev in events:
        typ = ev["type"]
        t = ev["time"]
        start = int(t*sr)
        if typ in mute_types or typ in lane_samples:
            kill = int(0.095*sr)
            a=max(0,start-int(0.012*sr)); b=min(len(out),start+kill)
            if b>a:
                fade=np.ones(b-a,dtype=np.float32)
                k=min(int(.012*sr),len(fade)//3)
                if k:
                    fade[:k]=np.linspace(1,0,k)
                    fade[-k:]=np.linspace(0,1,k)
                out[a:b]*=fade
        if typ in mute_types:
            continue
        sample_path = lane_samples.get(typ)
        if not sample_path: continue
        st=lane_settings.get(typ,{})
        samp=sample_transform(sample_path,sr,
                              volume=st.get("volume",1.0),
                              pitch=st.get("pitch",0.0),
                              speed=st.get("speed",1.0),
                              decay_ms=st.get("decay",450),
                              punch=st.get("punch",0.65))
        if len(samp)==0: continue
        a=start
        b=min(len(out),a+len(samp))
        if a<0 or a>=len(out): continue
        out[a:b] += samp[:b-a]
    peak=np.max(np.abs(out))+1e-9
    if peak>0.98: out*=0.98/peak
    return np.clip(out,-1,1)

def export_wav(path, y, sr):
    sf.write(path, y, sr, subtype="PCM_24")
