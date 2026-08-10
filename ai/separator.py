from __future__ import annotations
import os, subprocess, sys

def separate_drums(path,use_gpu=True,cb=None):
    import torch
    device='cuda' if use_gpu and torch.cuda.is_available() else 'cpu'
    out='cache/demucs'; os.makedirs(out,exist_ok=True)
    cmd=[sys.executable,'-m','demucs','--two-stems=drums','-n','htdemucs_ft','-d',device,'-o',out,path]
    if cb: cb(0.1)
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    subprocess.run(cmd,check=True,creationflags=flags)
    name=os.path.splitext(os.path.basename(path))[0]
    p=os.path.join(out,'htdemucs_ft',name,'drums.wav')
    if not os.path.isfile(p): raise FileNotFoundError('Demucs completed but drums.wav was not found.')
    from audio.loader import load_audio
    y,sr,_=load_audio(p,target_sr=44100,mono=True)
    if cb: cb(1.0)
    return y
