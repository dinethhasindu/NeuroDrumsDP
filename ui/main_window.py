from __future__ import annotations
import os, threading
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QPushButton,QLabel,QCheckBox,QComboBox,QProgressBar,QFileDialog,QMessageBox,QScrollArea,QFrame)
from PySide6.QtCore import Qt,QTimer,QObject,Signal
from ui.styles import DARK_THEME_QSS
from ui.sample_browser import SampleBrowser
from ui.event_inspector import EventInspector
from ui.lane_widget import LaneWidget
from ui.timeline_ruler import TimelineRuler
from ui.waveform_editor import WaveformEditor,OverviewWaveform
from core.constants import *
from core.models import ProjectState,LaneState
from audio.loader import load_audio
from audio.waveform_cache import WaveformCache
from audio.engine import AudioEngine
from audio.renderer import AudioRenderer
from audio.exporter import export_mix
from ai.pipeline import AnalysisPipeline
from project.manager import new_project,save_project,load_project

class Signals(QObject):
    loaded=Signal(object,object,object); failed=Signal(str); ai_progress=Signal(int,str,float); ai_done=Signal(bool,str,object,object,float,str)
    def __init__(self): super().__init__()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f'{APP_NAME} v{APP_VERSION}'); self.setMinimumSize(1420,860); self.setStyleSheet(DARK_THEME_QSS)
        self.project=new_project(); self.engine=AudioEngine(); self.cache=WaveformCache(); self.pipeline=AnalysisPipeline(); self.signals=Signals(); self.signals.loaded.connect(self._audio_ready); self.signals.failed.connect(self._load_failed); self.signals.ai_progress.connect(self._ai_progress); self.signals.ai_done.connect(self._ai_done)
        self.play_timer=QTimer(self); self.play_timer.setInterval(30); self.play_timer.timeout.connect(self._tick)
        self._build_ui(); self._build_menu()
    def _build_ui(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root); outer.setContentsMargins(10,10,10,10); outer.setSpacing(8)
        header=QFrame(); header.setObjectName('Header'); hl=QHBoxLayout(header); hl.setContentsMargins(14,10,14,10)
        title=QLabel(APP_NAME); title.setObjectName('Title'); hl.addWidget(title); sub=QLabel('  /  '+APP_SUBTITLE); sub.setObjectName('Subtitle'); hl.addWidget(sub); hl.addStretch()
        self.ai_label=QLabel('● AI: READY'); self.ai_label.setStyleSheet('color:#22c55e;font-weight:700;'); hl.addWidget(self.ai_label); outer.addWidget(header)
        tools=QHBoxLayout();
        self.btn_load=QPushButton('Load Audio'); self.btn_load.clicked.connect(self.load_audio_dialog); tools.addWidget(self.btn_load)
        self.btn_save=QPushButton('Save Project'); self.btn_save.clicked.connect(self.save_project); tools.addWidget(self.btn_save)
        self.btn_open=QPushButton('Open Project'); self.btn_open.clicked.connect(self.open_project); tools.addWidget(self.btn_open)
        self.btn_play=QPushButton('▶ Play'); self.btn_play.clicked.connect(self.play); tools.addWidget(self.btn_play)
        self.btn_stop=QPushButton('■ Stop'); self.btn_stop.clicked.connect(self.stop); tools.addWidget(self.btn_stop)
        tools.addSpacing(12); tools.addWidget(QLabel('Input'))
        self.stem=QCheckBox('Already a drum stem'); self.stem.setChecked(True); tools.addWidget(self.stem)
        tools.addWidget(QLabel('Sensitivity')); self.sensitivity=QComboBox(); self.sensitivity.addItems(['low','medium','high']); self.sensitivity.setCurrentText('medium'); tools.addWidget(self.sensitivity)
        self.btn_analyze=QPushButton('✦ Analyze AI'); self.btn_analyze.setObjectName('accent'); self.btn_analyze.clicked.connect(self.start_ai); tools.addWidget(self.btn_analyze)
        tools.addStretch(); self.zoom_label=QLabel('Zoom 120 px/s'); tools.addWidget(self.zoom_label)
        minus=QPushButton('−'); minus.setFixedWidth(32); minus.clicked.connect(lambda:self.set_zoom(self.editor.zoom/1.2)); tools.addWidget(minus)
        plus=QPushButton('+'); plus.setFixedWidth(32); plus.clicked.connect(lambda:self.set_zoom(self.editor.zoom*1.2)); tools.addWidget(plus)
        self.progress=QProgressBar(); self.progress.setFixedWidth(160); self.progress.setRange(0,100); self.progress.setValue(0); tools.addWidget(self.progress)
        self.btn_export=QPushButton('Export WAV'); self.btn_export.setObjectName('accent'); self.btn_export.clicked.connect(self.export); tools.addWidget(self.btn_export)
        outer.addLayout(tools)
        self.status=QLabel('Load a drum stem to begin.'); self.status.setStyleSheet('color:#7f8b9b;padding-left:4px;'); outer.addWidget(self.status)
        split=QSplitter(Qt.Horizontal); outer.addWidget(split,1)
        self.browser=SampleBrowser('samples'); split.addWidget(self.browser)
        center=QWidget(); cl=QVBoxLayout(center); cl.setContentsMargins(0,0,0,0); cl.setSpacing(6)
        ovcard=QFrame(); ovcard.setObjectName('Card'); ovl=QVBoxLayout(ovcard); ovl.setContentsMargins(10,8,10,8); ovtop=QHBoxLayout(); ovtop.addWidget(QLabel('WAVEFORM OVERVIEW')); self.file_label=QLabel('No audio loaded'); self.file_label.setStyleSheet('color:#7f8b9b'); ovtop.addWidget(self.file_label); ovtop.addStretch(); ovl.addLayout(ovtop)
        self.overview=OverviewWaveform(); self.overview.seek_requested.connect(self.seek); ovl.addWidget(self.overview); cl.addWidget(ovcard)
        timeline_row=QHBoxLayout(); timeline_row.setSpacing(0)
        self.lane_headers=QWidget(); self.lane_headers.setFixedWidth(LANE_HEADER_WIDTH); lh=QVBoxLayout(self.lane_headers); lh.setContentsMargins(0,34,0,0); lh.setSpacing(0)
        self.lane_widgets={}
        for n in LANE_NAMES:
            w=LaneWidget(n,LANE_COLORS[n]); w.mute_toggled.connect(self.lane_mute); w.solo_toggled.connect(self.lane_solo); w.volume_changed.connect(self.lane_volume); lh.addWidget(w); self.lane_widgets[n]=w
        timeline_row.addWidget(self.lane_headers)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(False); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn); self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.scroll.setFrameShape(QFrame.NoFrame)
        content=QWidget(); self.content=content; cv=QVBoxLayout(content); cv.setContentsMargins(0,0,0,0); cv.setSpacing(0)
        self.ruler=TimelineRuler(); cv.addWidget(self.ruler)
        self.editor=WaveformEditor(); self.editor.event_selected.connect(self.event_selected); self.editor.event_moved.connect(self.event_moved); self.editor.seek_requested.connect(self.seek); self.editor.sample_dropped.connect(self.sample_dropped); self.editor.zoom_changed.connect(self._zoom_changed); cv.addWidget(self.editor)
        self.scroll.setWidget(content); self.scroll.horizontalScrollBar().valueChanged.connect(self._scroll_changed); timeline_row.addWidget(self.scroll,1); cl.addLayout(timeline_row,1)
        split.addWidget(center)
        self.inspector=EventInspector(); self.inspector.event_changed.connect(self.inspector_changed); split.addWidget(self.inspector); split.setSizes([200,1000,300])
    def _build_menu(self):
        m=self.menuBar().addMenu('File'); m.addAction('Open Audio...',self.load_audio_dialog); m.addAction('Open Project...',self.open_project); m.addAction('Save Project',self.save_project); m.addSeparator(); m.addAction('Exit',self.close)
    def load_audio_dialog(self):
        p,_=QFileDialog.getOpenFileName(self,'Open Drum Audio','','Audio Files (*.wav *.mp3 *.flac *.ogg *.m4a *.aiff)')
        if p:self.load_audio_path(p)
    def load_audio_path(self,path):
        self.btn_load.setEnabled(False); self.btn_analyze.setEnabled(False); self.progress.setValue(5); self.ai_label.setText('● AI: WAITING'); self.ai_label.setStyleSheet('color:#fbbf24;font-weight:700;'); self.status.setText('Loading audio and building waveform…'); self.file_label.setText(os.path.basename(path))
        def work():
            try:
                y,sr,info=load_audio(path,target_sr=44100,mono=True); c=WaveformCache(); c.build(y,sr,cache_key=path); self.signals.loaded.emit(y,sr,(info,c))
            except Exception as e:self.signals.failed.emit(str(e))
        threading.Thread(target=work,daemon=True).start()
    def _audio_ready(self,y,sr,pair):
        info,c=pair; self.cache=c; self.engine.load(y,sr); self.project=new_project(); self.project.source_path=info.path; self.project.audio_info=info; self.project.bpm=120
        self.editor.set_data([],c,info.duration); self.overview.set_data(c,info.duration); self._update_content_width(); self.btn_load.setEnabled(True); self.btn_analyze.setEnabled(True); self.progress.setValue(0); self.status.setText(f'{info.filename}  •  {info.duration:.2f}s  •  {sr} Hz  •  waveform ready'); self.ai_label.setText('● AI: READY'); self.ai_label.setStyleSheet('color:#22c55e;font-weight:700;'); self.start_ai()
    def _load_failed(self,msg): self.btn_load.setEnabled(True); self.btn_analyze.setEnabled(True); self.ai_label.setText('● AI: ERROR'); self.ai_label.setStyleSheet('color:#ff4d6d;font-weight:700;'); QMessageBox.critical(self,'Audio load failed',msg)
    def start_ai(self):
        if not self.project.source_path:return
        self.btn_analyze.setEnabled(False); self.progress.setValue(0); self.ai_label.setText('● AI: ANALYZING'); self.ai_label.setStyleSheet('color:#60a5fa;font-weight:700;'); self.status.setText('AI is detecting hits. Waveform remains editable while analysis runs…')
        self.pipeline.run_async(self.project.source_path,self.sensitivity.currentText(),True,self.stem.isChecked(),self.signals.ai_progress.emit,self.signals.ai_done.emit)
    def _ai_progress(self,i,name,f): self.progress.setValue(int(((i+f)/6)*100)); self.status.setText(f'AI {i+1}/6  •  {name}  •  {int(f*100)}%')
    def _ai_done(self,ok,msg,events,info,bpm,mode):
        self.btn_analyze.setEnabled(True)
        if not ok:
            self.ai_label.setText('● AI: FAILED'); self.ai_label.setStyleSheet('color:#ff4d6d;font-weight:700;'); self.status.setText('Waveform is ready, but AI analysis failed: '+msg); return
        self.project.events=list(events); self.project.bpm=float(bpm); self.editor.set_data(self.project.events,self.cache,self.project.audio_info.duration,self.editor.zoom); self._update_content_width(); self.progress.setValue(100); self.ai_label.setText(f'● AI: {mode.upper()}'); self.ai_label.setStyleSheet('color:#22c55e;font-weight:700;'); self.status.setText(f'AI complete  •  {len(events)} events  •  {bpm:.1f} BPM')
    def _update_content_width(self):
        if not self.project.audio_info:return
        w=max(900,int(self.project.audio_info.duration*self.editor.zoom)+20); self.editor.setMinimumWidth(w); self.ruler.setMinimumWidth(w); self.content.setMinimumWidth(w); self.content.resize(max(w,self.scroll.viewport().width()),self.content.sizeHint().height()); self.ruler.set_state(self.project.audio_info.duration,self.editor.zoom,self.scroll.horizontalScrollBar().value(),self.project.bpm)
    def set_zoom(self,z): self.editor.set_zoom(z)
    def _zoom_changed(self,z): self.project.zoom=z; self.zoom_label.setText(f'Zoom {z:.0f} px/s'); self._update_content_width(); self.ruler.set_state(self.project.audio_info.duration if self.project.audio_info else 0,z,self.scroll.horizontalScrollBar().value(),self.project.bpm)
    def _scroll_changed(self,v): self.ruler.set_state(self.project.audio_info.duration if self.project.audio_info else 0,self.editor.zoom,v,self.project.bpm); self.editor.update()
    def event_selected(self,eid):
        ev=next((x for x in self.project.events if x.id==eid),None); self.inspector.set_event(ev)
    def event_moved(self,eid,start): self.status.setText(f'Event moved to {start:.3f}s')
    def inspector_changed(self,eid): self.editor.update()
    def sample_dropped(self,lane,path):
        for e in self.project.events:
            if e.type==lane:e.replacement_sample=path
        self.status.setText(f'Replacement sample assigned to {lane}: {os.path.basename(path)}'); self.editor.update()
    def lane_mute(self,lane,v): self.project.lane_states[lane].muted=v; [setattr(e,'muted',v) for e in self.project.events if e.type==lane]; self.editor.update()
    def lane_solo(self,lane,v): self.project.lane_states[lane].soloed=v
    def lane_volume(self,lane,v): self.project.lane_states[lane].volume=v
    def seek(self,t): self.engine.seek(t); self.editor.set_playhead(t); self.overview.set_playhead(t)
    def play(self):
        if self.engine.original is None:return
        try:self.engine.play(self.editor.playhead); self.play_timer.start(); self.btn_play.setText('❚❚ Playing')
        except Exception as e: QMessageBox.warning(self,'Playback unavailable',str(e))
    def stop(self): self.engine.stop(); self.play_timer.stop(); self.btn_play.setText('▶ Play')
    def _tick(self):
        if self.engine.is_playing:self.editor.set_playhead(self.engine.position); self.overview.set_playhead(self.engine.position)
        else:self.stop()
    def save_project(self):
        if not self.project.source_path:return
        p,_=QFileDialog.getSaveFileName(self,'Save NeuroDrums Project','','NeuroDrums Project (*.ndp)');
        if p:
            if not p.lower().endswith('.ndp'):p+='.ndp'
            try:save_project(self.project,p); self.status.setText('Project saved: '+os.path.basename(p))
            except Exception as e:QMessageBox.critical(self,'Save failed',str(e))
    def open_project(self):
        p,_=QFileDialog.getOpenFileName(self,'Open NeuroDrums Project','','NeuroDrums Project (*.ndp)');
        if not p:return
        try:
            pr=load_project(p); self.project=pr
            if pr.source_path and os.path.isfile(pr.source_path): self.load_audio_path(pr.source_path); self.status.setText('Project loaded; re-analyzing source…')
            else: QMessageBox.warning(self,'Audio missing','The project loaded, but its source audio path is not available on this computer.')
        except Exception as e:QMessageBox.critical(self,'Open failed',str(e))
    def export(self):
        if self.engine.original is None:return
        p,_=QFileDialog.getSaveFileName(self,'Export WAV','neurodrums_mix.wav','WAV (*.wav)');
        if not p:return
        try:
            mix,_=AudioRenderer(self.engine.sr).render(self.engine.original,self.project.events,self.project.lane_states); export_mix(mix,self.engine.sr,p,24); self.engine.set_processed(mix); self.status.setText('Exported '+os.path.basename(p))
        except Exception as e:QMessageBox.critical(self,'Export failed',str(e))
    def closeEvent(self,e): self.pipeline.cancel(); self.engine.stop(); e.accept()
