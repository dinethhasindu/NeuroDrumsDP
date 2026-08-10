import copy
import os
import threading
import time
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton,
    QLabel, QCheckBox, QComboBox, QProgressBar, QFileDialog, QMessageBox,
    QScrollArea, QFrame, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal
from ui.styles import DARK_THEME_QSS
from ui.sample_browser import SampleBrowser
from ui.event_inspector import EventInspector
from ui.lane_widget import LaneWidget
from ui.timeline_ruler import TimelineRuler
from ui.waveform_editor import WaveformEditor, OverviewWaveform
from core.constants import *
from core.models import ProjectState, LaneState
from audio.loader import load_audio
from audio.waveform_cache import WaveformCache
from audio.engine import AudioEngine
from audio.renderer import AudioRenderer
from audio.exporter import export_mix
from ai.pipeline import AnalysisPipeline
from ai.device import resolve_device
from project.manager import new_project, save_project, load_project
from core.history import HistoryManager
from core.commands import (
    MoveEventsCommand, DeleteEventsCommand, DuplicateEventsCommand,
    PropertyChangeCommand, BulkModifyCommand, SplitEventsCommand,
    PasteEventsCommand, ReplaceSampleCommand,
)


class Signals(QObject):
    loaded = Signal(object, object, object)
    failed = Signal(str)
    ai_progress = Signal(int, str, float)
    ai_done = Signal(bool, str, object, object, float, str)
    mix_ready = Signal(object)

    def __init__(self):
        super().__init__()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'{APP_NAME} v{APP_VERSION}')
        self.setMinimumSize(1420, 860)
        self.setStyleSheet(DARK_THEME_QSS)
        self.project = new_project()
        self.engine = AudioEngine()
        self.cache = WaveformCache()
        self.pipeline = AnalysisPipeline()
        self.renderer = AudioRenderer(DEFAULT_SR)
        self.signals = Signals()
        self.signals.loaded.connect(self._audio_ready)
        self.signals.failed.connect(self._load_failed)
        self.signals.ai_progress.connect(self._ai_progress)
        self.signals.ai_done.connect(self._ai_done)
        self.signals.mix_ready.connect(self._mix_ready)
        self.history = HistoryManager()
        self.history.on_changed = self._on_history_changed
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(30)
        self.play_timer.timeout.connect(self._tick)
        self._last_ai_mode = 'Analysis Fallback'
        self._last_ai_model = 'None'
        self._device_info = resolve_device('AUTO')
        self._pending_project = None
        self._mix_thread = None
        self._build_ui()
        self._build_menu()
        QShortcut(QKeySequence('Ctrl+Z'), self).activated.connect(self.history.undo)
        QShortcut(QKeySequence('Ctrl+Y'), self).activated.connect(self.history.redo)
        QShortcut(QKeySequence('Space'), self).activated.connect(self._toggle_play_stop)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        header = QFrame()
        header.setObjectName('Header')
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        title = QLabel(APP_NAME)
        title.setObjectName('Title')
        hl.addWidget(title)
        sub = QLabel('  /  ' + APP_SUBTITLE)
        sub.setObjectName('Subtitle')
        hl.addWidget(sub)
        hl.addStretch()
        self.ai_label = QLabel('● AI: READY')
        self.ai_label.setStyleSheet('color:#22c55e;font-weight:700;')
        hl.addWidget(self.ai_label)
        self.device_label = QLabel('CPU')
        self.device_label.setStyleSheet('color:#7f8b9b;font-weight:600;padding-left:12px;')
        hl.addWidget(self.device_label)
        outer.addWidget(header)

        tools = QHBoxLayout()
        self.btn_load = QPushButton('Load Audio')
        self.btn_load.clicked.connect(self.load_audio_dialog)
        tools.addWidget(self.btn_load)
        self.btn_save = QPushButton('Save Project')
        self.btn_save.clicked.connect(self.save_project)
        tools.addWidget(self.btn_save)
        self.btn_open = QPushButton('Open Project')
        self.btn_open.clicked.connect(self.open_project)
        tools.addWidget(self.btn_open)
        self.btn_play = QPushButton('▶ Play')
        self.btn_play.clicked.connect(self.play)
        tools.addWidget(self.btn_play)
        self.btn_pause = QPushButton('❚❚ Pause')
        self.btn_pause.clicked.connect(self.pause)
        tools.addWidget(self.btn_pause)
        self.btn_stop = QPushButton('■ Stop')
        self.btn_stop.clicked.connect(self.stop)
        tools.addWidget(self.btn_stop)
        tools.addSpacing(12)
        tools.addWidget(QLabel('Input'))
        self.stem = QCheckBox('Already a drum stem')
        self.stem.setChecked(True)
        tools.addWidget(self.stem)
        tools.addWidget(QLabel('Engine'))
        self.cb_engine = QComboBox()
        self.cb_engine.addItems(['AUTO', 'CPU', 'GPU'])
        self.cb_engine.currentTextChanged.connect(self._engine_changed)
        tools.addWidget(self.cb_engine)
        tools.addWidget(QLabel('Sensitivity'))
        self.sensitivity = QComboBox()
        self.sensitivity.addItems(['low', 'medium', 'high'])
        self.sensitivity.setCurrentText('medium')
        tools.addWidget(self.sensitivity)
        self.btn_analyze = QPushButton('✦ Analyze AI')
        self.btn_analyze.setObjectName('accent')
        self.btn_analyze.clicked.connect(self.start_ai)
        tools.addWidget(self.btn_analyze)
        tools.addStretch()
        self.chk_snap = QCheckBox('Snap')
        self.chk_snap.toggled.connect(self._snap_toggled)
        tools.addWidget(self.chk_snap)
        self.cb_grid = QComboBox()
        self.cb_grid.addItems(['1/4', '1/8', '1/16', '1/32'])
        self.cb_grid.currentTextChanged.connect(self._grid_changed)
        tools.addWidget(self.cb_grid)
        self.chk_triplet = QCheckBox('Triplet')
        self.chk_triplet.toggled.connect(self._grid_changed)
        tools.addWidget(self.chk_triplet)
        tools.addSpacing(10)
        self.zoom_label = QLabel('Zoom 120 px/s')
        tools.addWidget(self.zoom_label)
        minus = QPushButton('−')
        minus.setFixedWidth(32)
        minus.clicked.connect(lambda: self.set_zoom(self.editor.zoom / 1.2))
        tools.addWidget(minus)
        plus = QPushButton('+')
        plus.setFixedWidth(32)
        plus.clicked.connect(lambda: self.set_zoom(self.editor.zoom * 1.2))
        tools.addWidget(plus)
        self.btn_diag = QPushButton('Diagnostics')
        self.btn_diag.clicked.connect(self.show_diagnostics)
        tools.addWidget(self.btn_diag)
        self.btn_analysis = QPushButton('Analysis View')
        self.btn_analysis.clicked.connect(self.show_analysis_view)
        tools.addWidget(self.btn_analysis)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(160)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        tools.addWidget(self.progress)
        self.btn_export = QPushButton('Export WAV')
        self.btn_export.setObjectName('accent')
        self.btn_export.clicked.connect(self.export)
        tools.addWidget(self.btn_export)
        outer.addLayout(tools)

        self.status = QLabel('Load a drum stem to begin.')
        self.status.setStyleSheet('color:#7f8b9b;padding-left:4px;')
        outer.addWidget(self.status)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)
        self.browser = SampleBrowser('samples')
        split.addWidget(self.browser)
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        ovcard = QFrame()
        ovcard.setObjectName('Card')
        ovl = QVBoxLayout(ovcard)
        ovl.setContentsMargins(10, 8, 10, 8)
        ovtop = QHBoxLayout()
        ovtop.addWidget(QLabel('WAVEFORM OVERVIEW'))
        self.file_label = QLabel('No audio loaded')
        self.file_label.setStyleSheet('color:#7f8b9b')
        ovtop.addWidget(self.file_label)
        ovtop.addStretch()
        ovl.addLayout(ovtop)
        self.overview = OverviewWaveform()
        self.overview.seek_requested.connect(self.seek)
        ovl.addWidget(self.overview)
        cl.addWidget(ovcard)

        timeline_row = QHBoxLayout()
        timeline_row.setSpacing(0)
        self.lane_headers = QWidget()
        self.lane_headers.setFixedWidth(LANE_HEADER_WIDTH)
        lh = QVBoxLayout(self.lane_headers)
        lh.setContentsMargins(0, 34, 0, 0)
        lh.setSpacing(0)
        self.lane_widgets = {}
        for n in LANE_NAMES:
            w = LaneWidget(n, LANE_COLORS[n])
            w.mute_toggled.connect(self.lane_mute)
            w.solo_toggled.connect(self.lane_solo)
            w.volume_changed.connect(self.lane_volume)
            lh.addWidget(w)
            self.lane_widgets[n] = w
        timeline_row.addWidget(self.lane_headers)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        self.content = content
        cv = QVBoxLayout(content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        self.ruler = TimelineRuler()
        cv.addWidget(self.ruler)
        self.editor = WaveformEditor()
        self.editor.event_selected.connect(self.event_selected)
        self.editor.events_moved.connect(self.events_moved)
        self.editor.events_deleted.connect(self.events_deleted)
        self.editor.events_duplicated.connect(self.events_duplicated)
        self.editor.events_bulk_modified.connect(self.events_bulk_modified)
        self.editor.split_requested.connect(self.split_event)
        self.editor.replace_sample_requested.connect(self.replace_sample)
        self.editor.seek_requested.connect(self.seek)
        self.editor.sample_dropped.connect(self.sample_dropped)
        self.editor.zoom_changed.connect(self._zoom_changed)
        cv.addWidget(self.editor)
        self.scroll.setWidget(content)
        self.scroll.horizontalScrollBar().valueChanged.connect(self._scroll_changed)
        timeline_row.addWidget(self.scroll, 1)
        cl.addLayout(timeline_row, 1)
        split.addWidget(center)
        self.inspector = EventInspector()
        self.inspector.event_changed.connect(self.inspector_changed)
        self.inspector.event_property_changed.connect(self.event_property_changed)
        self.inspector.preview_requested.connect(self.preview_hit)
        self.inspector.replace_sample_requested.connect(self.replace_sample)
        split.addWidget(self.inspector)
        split.setSizes([200, 1000, 300])
        self._engine_changed(self.cb_engine.currentText())

    def _build_menu(self):
        m = self.menuBar().addMenu('File')
        m.addAction('Open Audio...', self.load_audio_dialog)
        m.addAction('Open Project...', self.open_project)
        m.addAction('Save Project', self.save_project)
        m.addSeparator()
        m.addAction('Exit', self.close)
        e = self.menuBar().addMenu('Edit')
        e.addAction('Undo', self.history.undo, QKeySequence('Ctrl+Z'))
        e.addAction('Redo', self.history.redo, QKeySequence('Ctrl+Y'))
        e.addSeparator()
        e.addAction('Cut', self.cut_events, QKeySequence('Ctrl+X'))
        e.addAction('Copy', self.copy_events, QKeySequence('Ctrl+C'))
        e.addAction('Paste', self.paste_events, QKeySequence('Ctrl+V'))
        e.addAction('Split at Playhead', self.split_events, QKeySequence('S'))

    def _engine_changed(self, text):
        self._device_info = resolve_device(text)
        dev = self._device_info
        vram = f' • {dev["vram_mb"]} MB VRAM' if dev['vram_mb'] else ''
        self.device_label.setText(f'{dev["backend"]}{vram}')
        if dev['status'] != 'Ready':
            self.status.setText(dev['status'])

    def _toggle_play_stop(self):
        if self.engine.is_playing:
            self.stop()
        else:
            self.play()

    def load_audio_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Open Drum Audio', '', 'Audio Files (*.wav *.mp3 *.flac *.ogg *.m4a *.aiff)')
        if p:
            self.load_audio_path(p)

    def load_audio_path(self, path, restore_project=None):
        self.btn_load.setEnabled(False)
        self.btn_analyze.setEnabled(False)
        self.progress.setValue(5)
        self.ai_label.setText('● AI: LOADING')
        self.ai_label.setStyleSheet('color:#fbbf24;font-weight:700;')
        self.status.setText('Loading audio and building waveform…')
        self.file_label.setText(os.path.basename(path))
        self._pending_project = restore_project

        def work():
            try:
                y, sr, info = load_audio(path, target_sr=44100, mono=True)
                c = WaveformCache()
                c.build(y, sr, cache_key=path)
                self.signals.loaded.emit(y, sr, (info, c))
            except Exception as e:
                self.signals.failed.emit(str(e))

        threading.Thread(target=work, daemon=True).start()

    def show_diagnostics(self):
        d = QDialog(self)
        d.setWindowTitle('System Diagnostics')
        d.setMinimumSize(460, 340)
        l = QVBoxLayout(d)
        dev = self._device_info
        l.addWidget(QLabel('<h2>AI ENGINE</h2>'))
        l.addWidget(QLabel(f'<b>Classifier:</b> {self._last_ai_mode}'))
        l.addWidget(QLabel(f'<b>Model:</b> {self._last_ai_model}'))
        l.addWidget(QLabel(f'<b>Device:</b> {dev["backend"]} ({dev["device_name"]})'))
        l.addWidget(QLabel(f'<b>Status:</b> {"Processing" if not self.btn_analyze.isEnabled() else "Ready"}'))
        if dev['vram_mb']:
            l.addWidget(QLabel(f'<b>VRAM:</b> {dev["vram_mb"]} MB'))
        l.addWidget(QLabel(f'<b>Project Events:</b> {len(self.project.events)}'))
        l.addWidget(QLabel(f'<b>Playback:</b> {"Playing" if self.engine.is_playing else "Stopped"}'))
        l.addStretch()
        btn = QPushButton('Close')
        btn.clicked.connect(d.accept)
        l.addWidget(btn)
        d.exec_()

    def show_analysis_view(self):
        d = QDialog(self)
        d.setWindowTitle('Analysis / Debug View')
        d.setMinimumSize(720, 480)
        l = QVBoxLayout(d)
        table = QTableWidget(len(self.project.events), 7)
        table.setHorizontalHeaderLabels(['Lane', 'Time', 'Duration', 'Confidence', 'Energy', 'Source', 'Features'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, ev in enumerate(sorted(self.project.events, key=lambda e: e.start)):
            table.setItem(i, 0, QTableWidgetItem(ev.type))
            table.setItem(i, 1, QTableWidgetItem(f'{ev.start:.4f}s'))
            table.setItem(i, 2, QTableWidgetItem(f'{ev.duration:.4f}s'))
            table.setItem(i, 3, QTableWidgetItem(f'{ev.confidence * 100:.0f}%'))
            table.setItem(i, 4, QTableWidgetItem(f'{getattr(ev, "onset_strength", 0):.3f}'))
            table.setItem(i, 5, QTableWidgetItem(getattr(ev, 'source', 'analysis')))
            feat_keys = list(getattr(ev, 'features', {}).keys())[:6]
            table.setItem(i, 6, QTableWidgetItem(', '.join(feat_keys) if feat_keys else '—'))
        l.addWidget(table)
        btn = QPushButton('Close')
        btn.clicked.connect(d.accept)
        l.addWidget(btn)
        d.exec_()

    def _audio_ready(self, y, sr, pair):
        info, c = pair
        self.cache = c
        self.engine.load(y, sr)
        self.renderer = AudioRenderer(sr)
        restore = self._pending_project
        self._pending_project = None
        if restore:
            self.project = restore
            self.history.clear()
            self.editor.set_data(self.project.events, c, info.duration, self.project.zoom, self.project.bpm)
            self.overview.set_data(c, info.duration)
            self.set_zoom(self.project.zoom)
            self.chk_snap.setChecked(self.project.snap_enabled)
            self._apply_grid(self.project.grid_fraction)
            self.seek(self.project.playhead)
            self._refresh_mix()
            self.btn_load.setEnabled(True)
            self.btn_analyze.setEnabled(True)
            self.progress.setValue(100)
            self.status.setText(f'Project restored  •  {len(self.project.events)} events  •  {info.filename}')
            self.ai_label.setText(f'● AI: {self._last_ai_mode.upper()}')
            self.editor.update()
        else:
            self.project = new_project()
            self.project.source_path = info.path
            self.project.audio_info = info
            self.project.bpm = 120
            self.history.clear()
            self.editor.set_data([], c, info.duration, bpm=self.project.bpm)
            self.overview.set_data(c, info.duration)
            self._update_content_width()
            self.btn_load.setEnabled(True)
            self.btn_analyze.setEnabled(True)
            self.progress.setValue(0)
            self.status.setText(f'{info.filename}  •  {info.duration:.2f}s  •  {sr} Hz  •  waveform ready')
            self.ai_label.setText('● AI: READY')
            self.ai_label.setStyleSheet('color:#22c55e;font-weight:700;')
            self.start_ai()

    def _load_failed(self, msg):
        self.btn_load.setEnabled(True)
        self.btn_analyze.setEnabled(True)
        self.ai_label.setText('● AI: ERROR')
        self.ai_label.setStyleSheet('color:#ff4d6d;font-weight:700;')
        QMessageBox.critical(self, 'Audio load failed', msg)

    def start_ai(self):
        if not self.project.source_path:
            return
        self.btn_analyze.setEnabled(False)
        self.progress.setValue(0)
        self.ai_label.setText('● AI: ANALYZING')
        self.ai_label.setStyleSheet('color:#60a5fa;font-weight:700;')
        self.status.setText('AI is detecting hits. Waveform remains editable while analysis runs…')
        engine = self.cb_engine.currentText()
        dev = resolve_device(engine)
        self._device_info = dev
        use_gpu = dev['device'] == 'cuda'
        if engine == 'GPU' and not dev['cuda_available']:
            self.status.setText('GPU unavailable — falling back to CPU for AI inference.')
        self.pipeline.run_async(
            self.project.source_path,
            self.sensitivity.currentText(),
            use_gpu,
            self.stem.isChecked(),
            self.signals.ai_progress.emit,
            self.signals.ai_done.emit,
        )

    def _ai_progress(self, i, name, f):
        self.progress.setValue(int(((i + f) / 6) * 100))
        self.status.setText(f'AI {i + 1}/6  •  {name}  •  {int(f * 100)}%')

    def _ai_done(self, ok, msg, events, info, bpm, mode):
        self.btn_analyze.setEnabled(True)
        parts = mode.split('|')
        self._last_ai_mode = parts[0] if parts else 'Analysis Fallback'
        self._last_ai_model = parts[1] if len(parts) > 1 else 'None'
        if not ok:
            self.ai_label.setText('● AI: FAILED')
            self.ai_label.setStyleSheet('color:#ff4d6d;font-weight:700;')
            self.status.setText('Waveform is ready, but AI analysis failed: ' + msg)
            return
        self.project.events = list(events)
        self.project.bpm = float(bpm)
        if info and info.path:
            self.project.audio_info = info
        self.history.clear()
        self.editor.set_data(self.project.events, self.cache, self.project.audio_info.duration, self.editor.zoom, self.project.bpm)
        self._update_content_width()
        self.progress.setValue(100)
        is_rf = self._last_ai_mode == 'Random Forest'
        color = '#22c55e' if is_rf else '#fbbf24'
        label = self._last_ai_mode if is_rf else 'Analysis Fallback'
        self.ai_label.setText(f'● AI: {label.upper()}')
        self.ai_label.setStyleSheet(f'color:{color};font-weight:700;')
        self.status.setText(f'AI complete  •  {len(events)} events  •  {bpm:.1f} BPM  •  Classifier: {label}')
        self._refresh_mix()

    def _refresh_mix(self):
        if self.engine.original is None:
            return

        def work():
            mix, _ = self.renderer.render(self.engine.original, self.project.events, self.project.lane_states)
            self.signals.mix_ready.emit(mix)

        if self._mix_thread and self._mix_thread.is_alive():
            return
        self._mix_thread = threading.Thread(target=work, daemon=True)
        self._mix_thread.start()

    def _mix_ready(self, mix):
        self.engine.set_processed(mix)

    def _update_content_width(self):
        if not self.project.audio_info:
            return
        w = max(900, int(self.project.audio_info.duration * self.editor.zoom) + 20)
        self.editor.setMinimumWidth(w)
        self.ruler.setMinimumWidth(w)
        self.content.setMinimumWidth(w)
        self.content.resize(max(w, self.scroll.viewport().width()), self.content.sizeHint().height())
        self.ruler.set_state(self.project.audio_info.duration, self.editor.zoom, self.scroll.horizontalScrollBar().value(), self.project.bpm)
        self.editor.update()

    def _on_history_changed(self):
        self._update_content_width()
        self._refresh_mix()
        if self.inspector.current_event:
            ev = next((x for x in self.project.events if x.id == self.inspector.current_event.id), None)
            if ev != self.inspector.current_event:
                self.inspector.set_event(ev)
        self.editor.update()

    def set_zoom(self, z):
        self.editor.set_zoom(z)

    def _zoom_changed(self, z):
        self.project.zoom = z
        self.zoom_label.setText(f'Zoom {z:.0f} px/s')
        self._update_content_width()
        dur = self.project.audio_info.duration if self.project.audio_info else 0
        self.ruler.set_state(dur, z, self.scroll.horizontalScrollBar().value(), self.project.bpm)

    def _scroll_changed(self, v):
        dur = self.project.audio_info.duration if self.project.audio_info else 0
        self.ruler.set_state(dur, self.editor.zoom, v, self.project.bpm)
        self.editor.update()
        if self.engine.is_playing:
            vp = self.scroll.viewport().width()
            ph = self.editor.playhead * self.editor.zoom
            if ph < v or ph > v + vp - 40:
                self.scroll.horizontalScrollBar().setValue(max(0, int(ph - vp * 0.3)))

    def _grid_frac(self):
        return {'1/4': 1 / 4, '1/8': 1 / 8, '1/16': 1 / 16, '1/32': 1 / 32}[self.cb_grid.currentText()]

    def _apply_grid(self, frac):
        texts = {'1/4': '1/4', '1/8': '1/8', '1/16': '1/16', '1/32': '1/32'}
        inv = {v: k for k, v in {'1/4': 1 / 4, '1/8': 1 / 8, '1/16': 1 / 16, '1/32': 1 / 32}.items()}
        if frac in inv:
            self.cb_grid.setCurrentText(inv[frac])

    def _snap_toggled(self, checked):
        frac = self._grid_frac()
        self.project.snap_enabled = checked
        self.editor.set_snap(checked, frac, self.chk_triplet.isChecked())

    def _grid_changed(self, *_):
        frac = self._grid_frac()
        self.project.grid_fraction = frac
        self.project.triplet_grid = self.chk_triplet.isChecked()
        self.editor.set_snap(self.chk_snap.isChecked(), frac, self.chk_triplet.isChecked())

    def event_selected(self, eid):
        ev = next((x for x in self.project.events if x.id == eid), None) if eid else None
        self.inspector.set_event(ev)

    def events_moved(self, ids, new_starts, old_starts):
        self.history.execute(MoveEventsCommand(self.project, ids, new_starts, old_starts, self._on_history_changed))
        self.status.setText(f'Moved {len(ids)} events')

    def events_deleted(self, ids):
        self.history.execute(DeleteEventsCommand(self.project, ids, self._on_history_changed))
        self.status.setText(f'Deleted {len(ids)} events')

    def events_duplicated(self, ids):
        self.history.execute(DuplicateEventsCommand(self.project, ids, self._on_history_changed))
        self.status.setText(f'Duplicated {len(ids)} events')

    def events_bulk_modified(self, old_states, new_states):
        self.history.execute(BulkModifyCommand(self.project, old_states, new_states, self._on_history_changed))

    def event_property_changed(self, eid, attr, old, new):
        if isinstance(old, bool) or isinstance(new, bool):
            self.history.execute(PropertyChangeCommand(self.project, eid, attr, new, old, self._on_history_changed))
        else:
            self.history.execute(PropertyChangeCommand(self.project, eid, attr, new, old, self._on_history_changed))

    def inspector_changed(self, eid):
        self.editor.update()
        self._refresh_mix()

    def copy_events(self):
        self.editor.copy_selection()

    def cut_events(self):
        self.editor.copy_selection()
        if self.editor.selected:
            self.events_deleted(list(self.editor.selected))

    def paste_events(self):
        cb, t, lane = self.editor.paste_at_playhead()
        if not cb:
            self.status.setText('Clipboard empty.')
            return
        lane = lane or (cb[0].type if cb else 'Kick')
        self.history.execute(PasteEventsCommand(self.project, cb, t, lane, self._on_history_changed))
        self.status.setText(f'Pasted {len(cb)} events')

    def split_events(self):
        if len(self.editor.selected) != 1:
            self.status.setText('Select exactly one event to split.')
            return
        self.split_event(list(self.editor.selected)[0], self.editor.playhead)

    def split_event(self, eid, split_time):
        self.history.execute(SplitEventsCommand(self.project, eid, split_time, self._on_history_changed))
        self.status.setText('Event split at playhead')

    def replace_sample(self, eid, path):
        old = {e.id: e.replacement_sample for e in self.project.events if e.id == eid}
        self.history.execute(ReplaceSampleCommand(self.project, [eid], path, old, self._on_history_changed))
        self.status.setText(f'Replacement: {os.path.basename(path)}')

    def preview_hit(self, eid):
        ev = next((x for x in self.project.events if x.id == eid), None)
        if not ev:
            return
        import sounddevice as sd
        mono = self.engine.original
        mix, sr = self.renderer.render_single_hit(ev, mono, self.project.lane_states)
        try:
            sd.play(mix, sr)
            self.status.setText(f'Preview: {ev.type}')
        except Exception as e:
            self.status.setText(f'Preview failed: {e}')

    def sample_dropped(self, lane, path):
        ids = [e.id for e in self.project.events if e.type == lane]
        if not ids:
            self.status.setText(f'No {lane} events to replace.')
            return
        old = {e.id: e.replacement_sample for e in self.project.events if e.id in ids}
        self.history.execute(ReplaceSampleCommand(self.project, ids, path, old, self._on_history_changed))
        self.status.setText(f'Replacement sample assigned to {lane}: {os.path.basename(path)}')

    def lane_mute(self, lane, v):
        self.project.lane_states[lane].muted = v
        for e in self.project.events:
            if e.type == lane:
                e.muted = v
        self.editor.update()
        self._refresh_mix()

    def lane_solo(self, lane, v):
        self.project.lane_states[lane].soloed = v
        self._refresh_mix()
        self.editor.update()

    def lane_volume(self, lane, v):
        self.project.lane_states[lane].volume = v
        self._refresh_mix()

    def seek(self, t):
        self.engine.seek(t)
        self.editor.set_playhead(t)
        self.overview.set_playhead(t)
        self.project.playhead = t

    def play(self):
        if self.engine.original is None:
            return
        self._refresh_mix()
        try:
            self.engine.play(self.editor.playhead)
            self.play_timer.start()
            self.btn_play.setText('❚❚ Playing')
        except Exception as e:
            QMessageBox.warning(self, 'Playback unavailable', str(e))

    def pause(self):
        self.engine.pause()
        self.btn_play.setText('▶ Play')

    def stop(self):
        self.engine.stop()
        self.play_timer.stop()
        self.btn_play.setText('▶ Play')

    def _tick(self):
        if self.engine.is_playing:
            pos = self.engine.position
            self.editor.set_playhead(pos)
            self.overview.set_playhead(pos)
            vp = self.scroll.viewport().width()
            sb = self.scroll.horizontalScrollBar()
            ph = pos * self.editor.zoom
            if ph < sb.value() or ph > sb.value() + vp - 40:
                sb.setValue(max(0, int(ph - vp * 0.3)))
        else:
            self.stop()

    def save_project(self):
        if not self.project.source_path:
            return
        self.project.zoom = self.editor.zoom
        self.project.playhead = self.editor.playhead
        self.project.snap_enabled = self.chk_snap.isChecked()
        self.project.grid_fraction = self._grid_frac()
        self.project.triplet_grid = self.chk_triplet.isChecked()
        p, _ = QFileDialog.getSaveFileName(self, 'Save NeuroDrums Project', '', 'NeuroDrums Project (*.ndp)')
        if p:
            if not p.lower().endswith('.ndp'):
                p += '.ndp'
            try:
                save_project(self.project, p)
                self.status.setText('Project saved: ' + os.path.basename(p))
            except Exception as e:
                QMessageBox.critical(self, 'Save failed', str(e))

    def open_project(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Open NeuroDrums Project', '', 'NeuroDrums Project (*.ndp)')
        if not p:
            return
        try:
            pr = load_project(p)
            if pr.source_path and os.path.isfile(pr.source_path):
                self.load_audio_path(pr.source_path, restore_project=pr)
                self.status.setText('Loading project…')
            else:
                self.project = pr
                QMessageBox.warning(self, 'Audio missing', 'Project loaded but source audio is unavailable.')
        except Exception as e:
            QMessageBox.critical(self, 'Open failed', str(e))

    def export(self):
        if self.engine.original is None:
            return
        p, _ = QFileDialog.getSaveFileName(self, 'Export WAV', 'neurodrums_mix.wav', 'WAV (*.wav)')
        if not p:
            return
        self.status.setText('Exporting…')
        self.progress.setValue(10)

        def work():
            try:
                mix, sr = self.renderer.render(self.engine.original, self.project.events, self.project.lane_states)
                export_mix(mix, sr, p, 24)
                self.engine.set_processed(mix)
                self.status.setText('Exported ' + os.path.basename(p))
                self.progress.setValue(100)
            except Exception as e:
                QMessageBox.critical(self, 'Export failed', str(e))

        threading.Thread(target=work, daemon=True).start()

    def closeEvent(self, e):
        self.pipeline.cancel()
        self.engine.stop()
        e.accept()
