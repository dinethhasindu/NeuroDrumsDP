from __future__ import annotations
import numpy as np

def group_rolls(events, max_gap=0.13, min_hits=3):
    if not events: return events
    events=sorted(events,key=lambda e:e.start)
    groups=[]; cur=[events[0]]
    for e in events[1:]:
        if e.start-cur[-1].start <= max_gap and e.type in ('Snare','Closed Hat','Open Hat','Clap') and cur[-1].type==e.type:
            cur.append(e)
        else:
            if len(cur)>=min_hits: groups.append(cur)
            cur=[e]
    if len(cur)>=min_hits: groups.append(cur)
    for g in groups:
        typ='Snare Roll' if g[0].type=='Snare' else 'Roll'
        for e in g: e.type=typ; e.subtype='FAST'; e.confidence=min(0.99,e.confidence+0.08)
    return events
