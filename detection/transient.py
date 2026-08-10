from __future__ import annotations
import numpy as np

def extract_features(y,sr,t):
    import librosa
    a=max(0,int((t-0.02)*sr)); b=min(len(y),int((t+0.22)*sr)); x=np.asarray(y[a:b],dtype=np.float32)
    if len(x)<256: x=np.pad(x,(0,256-len(x)))
    rms=float(np.sqrt(np.mean(x*x))+1e-9)
    S=np.abs(librosa.stft(x,n_fft=1024,hop_length=256))
    f=librosa.fft_frequencies(sr=sr,n_fft=1024)
    e=np.mean(S,axis=1)+1e-9
    total=float(e.sum())
    low=float(e[f<180].sum()/total); mid=float(e[(f>=180)&(f<2500)].sum()/total); high=float(e[f>=2500].sum()/total)
    centroid=float(librosa.feature.spectral_centroid(S=S,sr=sr).mean())
    bandwidth=float(librosa.feature.spectral_bandwidth(S=S,sr=sr).mean())
    flat=float(librosa.feature.spectral_flatness(S=S).mean())
    zcr=float(librosa.feature.zero_crossing_rate(x).mean())
    onset=float(librosa.onset.onset_strength(y=x,sr=sr,hop_length=256).max())
    sub=float(e[f<90].sum()/total)
    return {'low_energy':low,'mid_energy':mid,'high_energy':high,'subbass_energy':sub,'spectral_centroid':centroid,'spectral_bandwidth':bandwidth,'spectral_flatness':flat,'zcr':zcr,'rms':rms,'duration':len(x)/sr,'attack_frac':0.15,'decay_time':min(0.45,len(x)/sr),'percussive_ratio':0.7,'onset_strength_peak':onset}

def feature_vector(feats):
    keys=['low_energy','mid_energy','high_energy','subbass_energy','spectral_centroid','spectral_bandwidth','spectral_flatness','zcr','rms','duration','attack_frac','decay_time','percussive_ratio','onset_strength_peak']
    return np.asarray([float(feats.get(k,0.0)) for k in keys],dtype=np.float32)
