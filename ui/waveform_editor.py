from __future__ import annotations
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter,QPen,QBrush,QColor,QPainterPath,QMouseEvent,QWheelEvent
from PySide6.QtCore import Qt,Signal,QRectF
from core.constants import LANE_NAMES,LANE_COLORS,LANE_HEIGHT,MIN_ZOOM,MAX_ZOOM

class OverviewWaveform(QWidget):
    seek_requested=Signal(float)
    def __init__(self,parent=None):
        super().__init__(parent); self.cache=None; self.duration=0; self.playhead=0; self.setMinimumHeight(86); self.setStyleSheet('background:#0e1217;')
    def set_data(self,cache,duration): self.cache=cache; self.duration=duration; self.update()
    def set_playhead(self,p): self.playhead=p; self.update()
    def mousePressEvent(self,e):
        if self.duration and e.button()==Qt.LeftButton: self.seek_requested.emit(max(0,min(self.duration,e.position().x()/max(1,self.width())*self.duration)))
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.fillRect(self.rect(),QColor('#0e1217'))
        p.setPen(QPen(QColor('#252c35'))); p.drawRect(self.rect().adjusted(0,0,-1,-1))
        if not self.cache or self.duration<=0: return
        times,mn,mx=self.cache.get_peaks(0,self.duration,max(2,self.width()),self.width()/self.duration)
        if len(times):
            path=QPainterPath(); center=self.height()/2; scale=self.height()*0.42
            for i,(t,a,b) in enumerate(zip(times,mn,mx)):
                x=t/self.duration*self.width(); y1=center-b*scale; y2=center-a*scale
                if i==0:path.moveTo(x,y1)
                else:path.lineTo(x,y1)
            for t,a,b in zip(times[::-1],mn[::-1],mx[::-1]): path.lineTo(t/self.duration*self.width(),center-a*scale)
            path.closeSubpath(); p.setBrush(QBrush(QColor('#2f81f7'))); p.setPen(Qt.NoPen); p.drawPath(path)
            p.setPen(QPen(QColor('#7fb3ff'),1)); p.drawLine(0,int(center),self.width(),int(center))
        x=self.playhead/self.duration*self.width(); p.setPen(QPen(QColor('#ff4d6d'),2)); p.drawLine(int(x),0,int(x),self.height()); p.end()

class WaveformEditor(QWidget):
    event_selected=Signal(str); event_moved=Signal(str,float); seek_requested=Signal(float); sample_dropped=Signal(str,str); zoom_changed=Signal(float)
    def __init__(self,parent=None):
        super().__init__(parent); self.setAcceptDrops(True); self.setMouseTracking(True); self.setFocusPolicy(Qt.StrongFocus)
        self.events=[]; self.cache=None; self.duration=0; self.zoom=120; self.playhead=0; self.selected=None; self.hover=None; self.drag=None
    def set_data(self,events,cache,duration,zoom=None):
        self.events=events or []; self.cache=cache; self.duration=float(duration); self.zoom=float(zoom or self.zoom); self._resize(); self.update()
    def _resize(self): self.setMinimumWidth(max(900,int(self.duration*self.zoom)+20)); self.setMinimumHeight(len(LANE_NAMES)*LANE_HEIGHT)
    def set_zoom(self,z): self.zoom=max(MIN_ZOOM,min(MAX_ZOOM,float(z))); self._resize(); self.zoom_changed.emit(self.zoom); self.update()
    def set_playhead(self,p): self.playhead=max(0,min(self.duration,float(p))); self.update()
    def _lane_at(self,y):
        idx=int(y//LANE_HEIGHT); return LANE_NAMES[idx] if 0<=idx<len(LANE_NAMES) else None
    def _event_at(self,x,y):
        lane=self._lane_at(y); t=x/self.zoom
        if not lane:return None
        hits=[e for e in self.events if not e.removed and e.type==lane and e.start-0.015<=t<=max(e.end,e.start+0.045)]
        return min(hits,key=lambda e:abs(e.start-t)) if hits else None
    def mousePressEvent(self,e:QMouseEvent):
        if e.button()!=Qt.LeftButton:return
        x,y=float(e.position().x()),float(e.position().y()); ev=self._event_at(x,y)
        if ev:
            self.selected=ev.id; self.event_selected.emit(ev.id); self.drag=(x,ev.start); self.update()
        else:
            self.selected=None; self.event_selected.emit(''); self.seek_requested.emit(max(0,min(self.duration,x/self.zoom)))
    def mouseMoveEvent(self,e):
        x,y=float(e.position().x()),float(e.position().y()); ev=self._event_at(x,y); self.hover=ev.id if ev else None
        if self.drag and self.selected:
            dx=x-self.drag[0]; new=max(0,min(self.duration,self.drag[1]+dx/self.zoom))
            for obj in self.events:
                if obj.id==self.selected: obj.start=new; obj.end=new+obj.duration; break
        self.update()
    def mouseReleaseEvent(self,e):
        if e.button()==Qt.LeftButton and self.drag and self.selected:
            for obj in self.events:
                if obj.id==self.selected:self.event_moved.emit(obj.id,obj.start);break
            self.drag=None
    def wheelEvent(self,e:QWheelEvent):
        if e.modifiers() & Qt.ControlModifier:
            old=self.zoom; factor=1.18 if e.angleDelta().y()>0 else 1/1.18; self.set_zoom(old*factor); e.accept(); return
        super().wheelEvent(e)
    def dragEnterEvent(self,e): e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()
    def dropEvent(self,e):
        urls=e.mimeData().urls(); lane=self._lane_at(float(e.position().y()))
        if urls and lane:
            p=urls[0].toLocalFile();
            if p.lower().endswith(('.wav','.mp3','.flac','.ogg','.m4a')): self.sample_dropped.emit(lane,p); e.acceptProposedAction(); return
        e.ignore()
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.fillRect(self.rect(),QColor('#0d1116'))
        if not self.cache or self.duration<=0:return
        t0=0; t1=min(self.duration,self.width()/self.zoom); times,mn,mx=self.cache.get_peaks(t0,t1,max(100,self.width()),self.zoom)
        for i,lane in enumerate(LANE_NAMES):
            y=i*LANE_HEIGHT; bg=QColor('#11161c' if i%2==0 else '#151a20'); p.fillRect(0,y,self.width(),LANE_HEIGHT,bg)
            p.setPen(QPen(QColor('#252c34'),1)); p.drawLine(0,y+LANE_HEIGHT-1,self.width(),y+LANE_HEIGHT-1)
            # center line
            p.setPen(QPen(QColor(LANE_COLORS[lane]),1,Qt.DotLine)); p.setOpacity(.25); p.drawLine(0,y+LANE_HEIGHT/2,self.width(),y+LANE_HEIGHT/2); p.setOpacity(1)
        if len(times):
            for i,lane in enumerate(LANE_NAMES):
                center=i*LANE_HEIGHT+LANE_HEIGHT/2; scale=LANE_HEIGHT*0.39; p.setPen(QPen(QColor(LANE_COLORS[lane]),1)); p.setOpacity(.22)
                # stride to keep paint cost bounded
                stride=max(1,len(times)//max(1,self.width()//2))
                for j in range(0,len(times),stride):
                    x=times[j]*self.zoom; p.drawLine(int(x),int(center-mx[j]*scale),int(x),int(center-mn[j]*scale))
                p.setOpacity(1)
        for ev in self.events:
            if ev.removed or ev.start>t1 or ev.end<t0 or ev.type not in LANE_NAMES:continue
            li=LANE_NAMES.index(ev.type); x1=ev.start*self.zoom; x2=max(x1+6,ev.end*self.zoom); y=li*LANE_HEIGHT+10
            c=QColor(LANE_COLORS[ev.type]); c.setAlpha(180 if ev.uncertain else 230)
            if ev.id==self.selected: c=c.lighter(135)
            p.setBrush(QBrush(c)); p.setPen(QPen(QColor('#ffffff') if ev.id==self.selected else c.lighter(115),2 if ev.id==self.selected else 1)); p.drawRoundedRect(QRectF(x1,y,x2-x1,LANE_HEIGHT-20),5,5)
            p.setPen(QColor('#ffffff')); p.drawText(QRectF(x1+5,y+18,max(20,x2-x1-8),18),Qt.AlignLeft,ev.type)
            # confidence bar
            p.setPen(Qt.NoPen); p.setBrush(QColor(255,255,255,80)); p.drawRect(QRectF(x1,y+LANE_HEIGHT-29,max(3,(x2-x1)*ev.confidence),3))
        x=self.playhead*self.zoom; p.setPen(QPen(QColor('#ff335f'),2)); p.drawLine(int(x),0,int(x),self.height()); p.setBrush(QColor('#ff335f')); p.drawEllipse(int(x)-4,2,8,8)
        p.end()
