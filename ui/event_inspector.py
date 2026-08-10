from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QDoubleSpinBox, QComboBox, QFileDialog,
)
from PySide6.QtCore import Signal
from core.constants import LANE_NAMES


class EventInspector(QWidget):
    event_changed = Signal(str)
    event_property_changed = Signal(str, str, object, object)
    preview_requested = Signal(str)
    replace_sample_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_event = None
        self.setMinimumWidth(270)
        self.setMaximumWidth(320)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(14, 14, 14, 14)
        self.lay.setSpacing(10)
        self._build_empty()

    def _clear(self):
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build_empty(self):
        self._clear()
        a = QLabel('NO EVENT SELECTED')
        a.setObjectName('Section')
        self.lay.addWidget(a)
        b = QLabel('Click an event block to edit its timing, dynamics and replacement.')
        b.setWordWrap(True)
        b.setStyleSheet('color:#697586;')
        self.lay.addWidget(b)
        self.lay.addStretch()

    def set_event(self, e):
        self.current_event = e
        self._clear()
        if not e:
            self._build_empty()
            return
        title = QLabel('SELECTED EVENT')
        title.setObjectName('Section')
        self.lay.addWidget(title)
        name = QLabel(e.type)
        name.setStyleSheet('font-size:20px;font-weight:700;')
        self.lay.addWidget(name)
        if e.uncertain:
            unc = QLabel('⚠ Low confidence classification')
            unc.setStyleSheet('color:#fbbf24;font-weight:700;')
            self.lay.addWidget(unc)
        self.lay.addWidget(QLabel(f'Confidence  {e.confidence * 100:.0f}%'))
        if e.replacement_sample:
            rep = QLabel(f'● Replacement: {e.replacement_sample.split("/")[-1].split(chr(92))[-1]}')
            rep.setStyleSheet('color:#22c55e;font-weight:600;')
            rep.setWordWrap(True)
            self.lay.addWidget(rep)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel('Type'))
        type_box = QComboBox()
        type_box.addItems(LANE_NAMES)
        type_box.setCurrentText(e.type)
        type_row.addWidget(type_box)
        self.lay.addLayout(type_row)
        type_box.currentTextChanged.connect(lambda v: self._change('type', v))

        attributes = [
            ('Time s', 'start', 0, 99999, 0.001),
            ('Duration s', 'duration', 0.01, 10, 0.001),
            ('Offset ms', 'timing_offset_ms', -500, 500, 1),
            ('Velocity', 'velocity', 0, 1.5, 0.01),
            ('Volume dB', 'volume_db', -24, 12, 0.5),
            ('Pan', 'pan', -1, 1, 0.05),
            ('Pitch st', 'pitch', -24, 24, 0.5),
            ('Speed', 'speed', 0.1, 4, 0.05),
            ('Punch', 'punch', 0, 1, 0.05),
            ('Decay ms', 'decay_ms', 10, 2000, 10),
            ('Fade In ms', 'fade_in_ms', 0, 1000, 5),
            ('Fade Out ms', 'fade_out_ms', 0, 1000, 5),
        ]

        for label, attr, lo, hi, step in attributes:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            box = QDoubleSpinBox()
            box.setRange(lo, hi)
            box.setSingleStep(step)
            box.setValue(float(getattr(e, attr)))
            row.addWidget(box)
            self.lay.addLayout(row)
            box.valueChanged.connect(lambda v, a=attr: self._change(a, v))

        buttons = QHBoxLayout()
        mute = QPushButton('Mute' if not e.muted else 'Unmute')
        remove = QPushButton('Remove')
        remove.setObjectName('danger')
        preview = QPushButton('Preview Hit')
        preview.setObjectName('accent')
        replace = QPushButton('Replace Sample')
        buttons.addWidget(mute)
        buttons.addWidget(remove)
        self.lay.addLayout(buttons)
        btn2 = QHBoxLayout()
        btn2.addWidget(preview)
        btn2.addWidget(replace)
        self.lay.addLayout(btn2)

        mute.clicked.connect(lambda: self._change('muted', not e.muted))
        remove.clicked.connect(lambda: self._change('removed', True))
        preview.clicked.connect(lambda: self.preview_requested.emit(self.current_event.id))
        replace.clicked.connect(lambda: self._pick_sample())
        self.lay.addStretch()

    def _pick_sample(self):
        if not self.current_event:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Replace Sample', '', 'Audio (*.wav *.flac *.ogg *.mp3)')
        if path:
            self.replace_sample_requested.emit(self.current_event.id, path)

    def _change(self, attr, val):
        if self.current_event is None:
            return
        old = getattr(self.current_event, attr)
        if isinstance(old, bool):
            if old == val:
                return
        elif isinstance(old, (int, float)) and isinstance(val, (int, float)):
            if abs(float(old) - float(val)) < 1e-6:
                return
        elif old == val:
            return
        setattr(self.current_event, attr, val)
        if attr == 'start':
            self.current_event.end = self.current_event.start + self.current_event.duration
        elif attr == 'duration':
            self.current_event.end = self.current_event.start + self.current_event.duration
        self.event_property_changed.emit(self.current_event.id, attr, old, val)
        self.event_changed.emit(self.current_event.id)
