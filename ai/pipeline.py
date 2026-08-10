from __future__ import annotations
import os, subprocess, threading
from typing import Callable
import numpy as np
from core.models import DrumEvent, AudioInfo
from detection.onset import detect_onsets, detect_bpm
from detection.transient import extract_features
from detection.roll import group_rolls
from ai.classifier import DrumClassifier

STAGES=['Loading audio','Preparing drum signal','Detecting transients','Extracting features','AI classifying events','Grouping rolls']
class AnalysisPipeline:
    def __init__(self): self.classifier=DrumClassifier(); self._cancel=False; self.thread=None
    def cancel(self): self._cancel=True
    def run_async(self,path,sensitivity='medium',use_gpu=True,skip_separation=True,progress_cb=None,done_cb=None):
        self._cancel=False
        self.thread=threading.Thread(target=self._run,args=(path,sensitivity,use_gpu,skip_separation,progress_cb,done_cb),daemon=True); self.thread.start()
    def _p(self,cb,i,name,f):
        if cb: cb(i,name,float(max(0,min(1,f))))
    def _run(self,path,sensitivity,use_gpu,skip,cb,done):
        try:
            from audio.loader import load_audio
            self._p(cb,0,STAGES[0],0); y,sr,info=load_audio(path,target_sr=44100,mono=True); self._p(cb,0,STAGES[0],1)
            if self._cancel: raise InterruptedError('Cancelled')
            drum=y
            if skip:
                self._p(cb,1,STAGES[1],1)
            else:
                self._p(cb,1,STAGES[1],0.05)
                from ai.separator import separate_drums
                from ai.device import resolve_device
                dev = resolve_device('GPU' if use_gpu else 'CPU')
                drum=separate_drums(path, dev['device'] == 'cuda', cb=lambda f:self._p(cb,1,STAGES[1],f))
                self._p(cb,1,STAGES[1],1)
            times,strengths=detect_onsets(drum,sr,sensitivity); bpm=detect_bpm(drum,sr); self._p(cb,2,STAGES[2],1)
            feats=[]
            for i,(t,s) in enumerate(zip(times,strengths)):
                if self._cancel: raise InterruptedError('Cancelled')
                f=extract_features(drum,sr,float(t)); f['onset_strength_peak']=float(s); feats.append(f)
                self._p(cb,3,STAGES[3],(i+1)/max(1,len(times)))
            events=[]
            for i,(t,f) in enumerate(zip(times,feats)):
                typ,conf,_=self.classifier.classify(f)
                dur=min(0.35,max(0.035,f.get('decay_time',0.08)+0.02))
                e=DrumEvent(type=typ,start=float(t),end=float(t+dur),duration=dur,velocity=float(np.clip(f['rms']*5,0.15,1)),confidence=float(conf),uncertain=conf<0.45,low_energy=f['low_energy'],mid_energy=f['mid_energy'],high_energy=f['high_energy'],spectral_centroid=f['spectral_centroid'],zcr=f['zcr'],onset_strength=float(f.get('onset_strength_peak',0)),source='analysis',features={k:float(v) for k,v in f.items() if isinstance(v,(int,float))})
                events.append(e); self._p(cb,4,STAGES[4],(i+1)/max(1,len(times)))
            events=group_rolls(events); self._p(cb,5,STAGES[5],1)
            mode = f"{self.classifier.mode}|{self.classifier.model_name}"
            if done: done(True,'',events,info,bpm,mode)
        except Exception as exc:
            mode = f"{self.classifier.mode}|{self.classifier.model_name}"
            if done: done(False,str(exc),[],AudioInfo(path=path,filename=os.path.basename(path)),120.0,mode)
