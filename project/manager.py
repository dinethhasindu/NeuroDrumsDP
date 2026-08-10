from __future__ import annotations
import json, os
from core.models import ProjectState, DrumEvent, LaneState, AudioInfo
from core.constants import LANE_NAMES, LANE_COLORS

def new_project():
    p=ProjectState()
    p.lane_states={n:LaneState(n,color=LANE_COLORS[n]) for n in LANE_NAMES}
    return p

def save_project(p,path):
    with open(path,'w',encoding='utf-8') as f: json.dump(p.to_dict(),f,indent=2)

def load_project(path):
    with open(path,'r',encoding='utf-8') as f: d=json.load(f)
    p=new_project(); p.version=d.get('version','1.1'); p.source_path=d.get('source_path',''); p.drum_stem_path=d.get('drum_stem_path',''); p.bpm=float(d.get('bpm',120)); p.zoom=float(d.get('zoom',120)); p.playhead=float(d.get('playhead',0))
    p.events=[DrumEvent.from_dict(x) for x in d.get('events',[])]
    for n,x in d.get('lanes',{}).items():
        if n in p.lane_states:
            for k,v in x.items():
                if hasattr(p.lane_states[n],k): setattr(p.lane_states[n],k,v)
    ai=d.get('audio_info')
    p.audio_info=AudioInfo(**ai) if ai else None
    return p
