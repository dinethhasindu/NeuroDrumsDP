"""
NeuroDrums AI - Event Inspector UI.
Right panel for editing parameters of the currently selected DrumEvent.
"""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QDoubleSpinBox,
    QPushButton, QGroupBox, QComboBox, QCheckBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from core.models import DrumEvent

class EventInspector(QWidget):
    """
    Allows editing properties of a single selected DrumEvent.
    """
    
    event_changed = Signal(str)  # Emits event ID when changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_event = None
        self._init_ui()

    def _init_ui(self):
        self.setFixedWidth(260)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        self.lbl_header = QLabel("No Event Selected")
        self.lbl_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_header)
        
        # Info
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #888;")
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        # Actions
        act_layout = QHBoxLayout()
        self.btn_mute = QPushButton("Mute")
        self.btn_mute.setCheckable(True)
        self.btn_mute.clicked.connect(self._on_edit)
        
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setStyleSheet("color: #ff4d6d;")
        self.btn_remove.clicked.connect(self._on_remove)
        
        act_layout.addWidget(self.btn_mute)
        act_layout.addWidget(self.btn_remove)
        layout.addLayout(act_layout)

        # --- Timing Group ---
        grp_time = QGroupBox("Timing & Velocity")
        lt_time = QVBoxLayout(grp_time)
        
        self.spin_offset = self._create_row(lt_time, "Nudge (ms)", -100, 100, 0)
        self.spin_velocity = self._create_row(lt_time, "Velocity", 0.0, 1.0, 0.8, step=0.05)
        layout.addWidget(grp_time)

        # --- Envelope Group ---
        grp_env = QGroupBox("Envelope")
        lt_env = QVBoxLayout(grp_env)
        
        self.spin_punch = self._create_row(lt_env, "Punch", 0.0, 1.0, 0.65, step=0.05)
        self.spin_decay = self._create_row(lt_env, "Decay (ms)", 10, 2000, 450)
        self.spin_pitch = self._create_row(lt_env, "Pitch (st)", -24, 24, 0)
        layout.addWidget(grp_env)
        
        # --- Mix Group ---
        grp_mix = QGroupBox("Mix")
        lt_mix = QVBoxLayout(grp_mix)
        
        self.spin_vol = self._create_row(lt_mix, "Volume (dB)", -24, 24, 0)
        self.spin_pan = self._create_row(lt_mix, "Pan", -1.0, 1.0, 0.0, step=0.1)
        layout.addWidget(grp_mix)

        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        self.setEnabled(False)

    def _create_row(self, layout, label_text, min_val, max_val, default, step=1.0):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSingleStep(step)
        spin.setDecimals(2 if step < 1.0 else 1)
        spin.valueChanged.connect(self._on_edit)
        
        row.addWidget(lbl)
        row.addWidget(spin)
        layout.addLayout(row)
        return spin

    def set_event(self, event: DrumEvent):
        self.current_event = event
        if not event:
            self.setEnabled(False)
            self.lbl_header.setText("No Event Selected")
            self.lbl_info.setText("")
            return

        self.setEnabled(True)
        self.lbl_header.setText(f"{event.type} Event")
        self.lbl_header.setStyleSheet(f"font-weight: bold; font-size: 14px; color: #ffffff;")
        
        conf_str = f"Confidence: {event.confidence*100:.1f}%"
        if event.uncertain:
            conf_str += " (Uncertain)"
        time_str = f"Time: {event.start:.3f}s"
        self.lbl_info.setText(f"{time_str}\n{conf_str}")
        
        # Block signals to update UI without triggering edits
        self._block_all(True)
        
        self.btn_mute.setChecked(event.muted)
        self.spin_offset.setValue(event.timing_offset_ms)
        self.spin_velocity.setValue(event.velocity)
        self.spin_punch.setValue(event.punch)
        self.spin_decay.setValue(event.decay_ms)
        self.spin_pitch.setValue(event.pitch)
        self.spin_vol.setValue(event.volume_db)
        self.spin_pan.setValue(event.pan)
        
        self._block_all(False)

    def _block_all(self, state: bool):
        self.btn_mute.blockSignals(state)
        self.spin_offset.blockSignals(state)
        self.spin_velocity.blockSignals(state)
        self.spin_punch.blockSignals(state)
        self.spin_decay.blockSignals(state)
        self.spin_pitch.blockSignals(state)
        self.spin_vol.blockSignals(state)
        self.spin_pan.blockSignals(state)

    def _on_edit(self, *_):
        if not self.current_event:
            return
            
        e = self.current_event
        e.muted = self.btn_mute.isChecked()
        e.timing_offset_ms = self.spin_offset.value()
        e.velocity = self.spin_velocity.value()
        e.punch = self.spin_punch.value()
        e.decay_ms = self.spin_decay.value()
        e.pitch = self.spin_pitch.value()
        e.volume_db = self.spin_vol.value()
        e.pan = self.spin_pan.value()
        
        self.event_changed.emit(e.id)

    def _on_remove(self):
        if self.current_event:
            self.current_event.removed = True
            self.event_changed.emit(self.current_event.id)
            self.set_event(None)
