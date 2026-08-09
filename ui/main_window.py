"""
NeuroDrums AI - Main Window.
PySide6 QMainWindow connecting all panels and audio engine.
"""
from __future__ import annotations
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QSplitter, QMenuBar, QMenu, QFileDialog, QMessageBox,
    QPushButton, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal

from ui.styles import DARK_THEME_QSS
from ui.sample_browser import SampleBrowser
from ui.event_inspector import EventInspector
from ui.lane_widget import LaneWidget
from ui.timeline_ruler import TimelineRuler
from ui.waveform_editor import WaveformEditor

from core.models import ProjectState, LaneState
from core.constants import LANE_NAMES, LANE_COLORS, LANE_HEIGHT, APP_NAME, APP_VERSION
from audio.engine import AudioEngine
from audio.renderer import AudioRenderer
from audio.exporter import export_mix
from audio.loader import load_audio
from audio.waveform_cache import WaveformCache
from ai.pipeline import AnalysisPipeline

class PipelineBridge(QObject):
    progress = Signal(int, str, float)
    done = Signal(bool, str, list, object, float)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(DARK_THEME_QSS)

        self.project = ProjectState()
        self.audio_engine = AudioEngine()
        self.wave_cache = WaveformCache()
        self.pipeline = AnalysisPipeline()
        
        self.bridge = PipelineBridge()
        self.bridge.progress.connect(self._on_pipeline_progress)
        self.bridge.done.connect(self._on_pipeline_done)
        
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(30) # ~33fps
        self.play_timer.timeout.connect(self._update_playhead)

        self._init_ui()
        self._init_menu()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # --- Top Toolbar ---
        toolbar = QHBoxLayout()
        self.btn_load = QPushButton("Load Audio")
        self.btn_load.clicked.connect(self._on_load_audio)
        
        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self._on_play)
        
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self._on_stop)

        self.chk_skip_separation = QCheckBox("Input is already a drum stem")
        self.chk_skip_separation.setChecked(True)
        self.chk_skip_separation.setToolTip(
            "Leave this enabled for drum stems. Disable it only for a full song, "
            "which must be separated with Demucs first."
        )
        
        self.btn_export = QPushButton("Export")
        self.btn_export.setProperty("class", "AccentButton")
        self.btn_export.clicked.connect(self._on_export)
        
        self.lbl_status = QLabel("Ready")
        
        toolbar.addWidget(self.btn_load)
        toolbar.addWidget(self.btn_play)
        toolbar.addWidget(self.btn_stop)
        toolbar.addWidget(self.chk_skip_separation)
        toolbar.addStretch()
        toolbar.addWidget(self.lbl_status)
        toolbar.addWidget(self.btn_export)
        
        main_layout.addLayout(toolbar)

        # --- Main Splitter ---
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # 1. Left Panel (Sample Browser)
        self.browser = SampleBrowser("samples")
        self.splitter.addWidget(self.browser)

        # 2. Center Panel (Timeline + Lanes + Waveform)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        
        # Timeline Ruler
        self.timeline = TimelineRuler()
        center_layout.addWidget(self.timeline)
        
        # Scroll area for lanes and waveform
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # The content of the scroll area
        scroll_content = QWidget()
        scroll_layout = QHBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)
        
        # Lane headers (Left side of scroll content)
        lane_header_container = QWidget()
        lane_header_layout = QVBoxLayout(lane_header_container)
        lane_header_layout.setContentsMargins(0, 0, 0, 0)
        lane_header_layout.setSpacing(0)
        
        self.lane_widgets = {}
        for name in LANE_NAMES:
            lw = LaneWidget(name, LANE_COLORS.get(name, "#ffffff"))
            lane_header_layout.addWidget(lw)
            self.lane_widgets[name] = lw
            lw.mute_toggled.connect(self._on_lane_mute_changed)
            lw.solo_toggled.connect(self._on_lane_solo_changed)
            lw.volume_changed.connect(self._on_lane_volume_changed)
        lane_header_layout.addStretch()
        scroll_layout.addWidget(lane_header_container)
        
        # Waveform Editor (Right side of scroll content)
        self.editor = WaveformEditor()
        self.editor.setMinimumHeight(len(LANE_NAMES) * LANE_HEIGHT)
        self.editor.setMinimumWidth(2000) # dynamic later
        scroll_layout.addWidget(self.editor, 1)
        
        scroll_area.setWidget(scroll_content)
        center_layout.addWidget(scroll_area)
        
        self.splitter.addWidget(center_widget)

        # 3. Right Panel (Event Inspector)
        self.inspector = EventInspector()
        self.inspector.event_changed.connect(self._on_event_changed)
        self.splitter.addWidget(self.inspector)

        # Connect editor signals
        self.editor.event_selected.connect(self._on_event_selected)
        self.editor.event_moved.connect(self._on_event_moved)
        self.editor.seek_requested.connect(self._on_seek_requested)
        self.editor.sample_dropped.connect(self._on_sample_dropped)

        # Set splitter sizes
        self.splitter.setSizes([200, 800, 260])
        
        # Sync scrolling
        self.scroll_bar = scroll_area.horizontalScrollBar()
        self.scroll_bar.valueChanged.connect(self._on_scroll)

    def _init_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Open Audio...", self._on_load_audio)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)
        
    def _on_load_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Audio", "", "Audio Files (*.wav *.mp3 *.flac *.m4a *.ogg)"
        )
        if not path:
            return
            
        self.lbl_status.setText(f"Loading {os.path.basename(path)}...")
        self.btn_load.setEnabled(False)
        # Start pipeline
        self.pipeline.run_async(
            audio_path=path,
            sensitivity="medium",
            use_gpu=True,
            skip_separation=self.chk_skip_separation.isChecked(),
            progress_cb=self.bridge.progress.emit,
            done_cb=self.bridge.done.emit
        )

    def _on_pipeline_progress(self, stage_idx: int, stage_name: str, fraction: float):
        # Must use QTimer or signal to update UI from thread, but PySide6 often handles simple QLabel setText ok.
        # Safest way in production is via Signals. For this app, we'll just set it.
        pct = int(fraction * 100)
        self.lbl_status.setText(f"Stage {stage_idx+1}/6: {stage_name} ({pct}%)")

    def _on_pipeline_done(self, success, error_msg, events, audio_info, bpm):
        self.btn_load.setEnabled(True)
        if not success:
            QMessageBox.critical(self, "Error", f"Analysis failed:\n{error_msg}")
            self.lbl_status.setText("Analysis failed.")
            return

        self.lbl_status.setText("Building waveform cache...")
        
        # Build project state
        self.project = ProjectState()
        self.project.source_path = audio_info.path
        self.project.events = events
        self.project.audio_info = audio_info
        self.project.bpm = bpm
        
        for name in LANE_NAMES:
            self.project.lane_states[name] = LaneState(name=name, color=LANE_COLORS.get(name, "#888888"))

        # Load audio into engine
        y, sr, _ = load_audio(audio_info.path, target_sr=44100, mono=True)
        self.audio_engine.load(y, sr)
        
        # Build cache
        self.wave_cache.build(y, sr, cache_key=os.path.basename(audio_info.path))
        
        # Update UI
        self.editor.set_data(self.project.events, self.wave_cache, audio_info.duration)
        self._on_scroll(self.scroll_bar.value())
        
        # Update width based on duration and zoom
        width = int(audio_info.duration * self.editor.zoom)
        self.editor.setMinimumWidth(max(width, self.editor.parentWidget().width()))
        
        self.lbl_status.setText("Ready.")

    def _on_scroll(self, val):
        self.editor.scroll_x = val
        self.timeline.update_state(
            self.project.audio_info.duration if self.project.audio_info else 0,
            self.editor.zoom,
            val,
            self.project.bpm,
            self.lane_widgets[LANE_NAMES[0]].width(),
        )
        self.editor.update()

    def _on_event_selected(self, event_id: str):
        if not event_id:
            self.inspector.set_event(None)
            return
            
        for e in self.project.events:
            if e.id == event_id:
                self.inspector.set_event(e)
                break

    def _on_event_changed(self, event_id: str):
        self.editor.update()

    def _on_event_moved(self, event_id: str, start: float):
        if self.inspector.current_event and self.inspector.current_event.id == event_id:
            self.inspector.set_event(self.inspector.current_event)
        self.editor.update()

    def _on_seek_requested(self, position: float):
        self.audio_engine.seek(position)
        self.editor.set_playhead(position)

    def _on_lane_mute_changed(self, lane: str, muted: bool):
        state = self.project.lane_states.get(lane)
        if state:
            state.muted = muted

    def _on_lane_solo_changed(self, lane: str, soloed: bool):
        state = self.project.lane_states.get(lane)
        if state:
            state.soloed = soloed

    def _on_lane_volume_changed(self, lane: str, volume: float):
        state = self.project.lane_states.get(lane)
        if state:
            state.volume = volume

    def _on_sample_dropped(self, lane: str, path: str):
        """Assign a dragged sample to every event in the target lane."""
        state = self.project.lane_states.get(lane)
        if state:
            state.replacement_sample = path
        affected = 0
        for event in self.project.events:
            if event.type == lane:
                event.replacement_sample = path
                affected += 1
        self.lbl_status.setText(
            f"Assigned {os.path.basename(path)} to {lane} ({affected} events)"
        )
        
    def _on_play(self):
        if self.audio_engine.original is not None:
            self.audio_engine.play(start=self.editor.playhead_pos)
            self.play_timer.start()
            
    def _on_stop(self):
        self.audio_engine.stop()
        self.play_timer.stop()
        
    def _update_playhead(self):
        if self.audio_engine.is_playing:
            self.editor.set_playhead(self.audio_engine.position)
        else:
            self.play_timer.stop()

    def _on_export(self):
        if self.audio_engine.original is None:
            QMessageBox.information(self, "Export", "Load audio before exporting.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Mix", "neurodrums_mix.wav", "WAV Audio (*.wav)"
        )
        if not path:
            return
        if not path.lower().endswith(".wav"):
            path += ".wav"

        try:
            renderer = AudioRenderer(self.audio_engine.sr)
            mix, _ = renderer.render(
                self.audio_engine.original, self.project.events, self.project.lane_states
            )
            export_mix(mix, self.audio_engine.sr, path)
            self.audio_engine.set_processed(mix)
            self.lbl_status.setText(f"Exported {os.path.basename(path)}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def closeEvent(self, event):
        self.pipeline.cancel()
        self.audio_engine.stop()
        event.accept()
