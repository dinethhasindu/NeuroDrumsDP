"""
NeuroDrums AI - Lane Header Widget.
Displays the lane name, color, Mute, Solo, and Volume controls.
"""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider
)
from PySide6.QtCore import Qt, Signal

class LaneWidget(QWidget):
    """
    Header controls for a single drum lane (Kick, Snare, etc.)
    """
    
    mute_toggled = Signal(str, bool)
    solo_toggled = Signal(str, bool)
    volume_changed = Signal(str, float)

    def __init__(self, name: str, color: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.color = color
        self.is_muted = False
        self.is_soloed = False
        self._init_ui()

    def _init_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: #2a2a2a; border-right: 2px solid {self.color};")
        self.setFixedWidth(180)
        self.setFixedHeight(90)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # Label
        self.lbl_name = QLabel(self.name)
        self.lbl_name.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {self.color}; border: none;")
        main_layout.addWidget(self.lbl_name)

        # Controls HBox
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(5)

        self.btn_mute = QPushButton("M")
        self.btn_mute.setFixedSize(24, 24)
        self.btn_mute.setCheckable(True)
        self.btn_mute.setStyleSheet("QPushButton { border-radius: 12px; font-weight: bold; background-color: #333; } QPushButton:checked { background-color: #ff4d6d; color: white; }")
        self.btn_mute.toggled.connect(self._on_mute)
        
        self.btn_solo = QPushButton("S")
        self.btn_solo.setFixedSize(24, 24)
        self.btn_solo.setCheckable(True)
        self.btn_solo.setStyleSheet("QPushButton { border-radius: 12px; font-weight: bold; background-color: #333; } QPushButton:checked { background-color: #ffbe0b; color: black; }")
        self.btn_solo.toggled.connect(self._on_solo)

        ctrl_layout.addWidget(self.btn_mute)
        ctrl_layout.addWidget(self.btn_solo)
        ctrl_layout.addStretch()

        main_layout.addLayout(ctrl_layout)

        # Volume Slider
        vol_layout = QHBoxLayout()
        vol_icon = QLabel("Vol")
        vol_icon.setStyleSheet("font-size: 10px; color: #888; border: none;")
        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(80) # Default ~ 0dB
        self.slider_vol.setStyleSheet("border: none;")
        self.slider_vol.valueChanged.connect(self._on_vol)
        
        vol_layout.addWidget(vol_icon)
        vol_layout.addWidget(self.slider_vol)
        
        main_layout.addLayout(vol_layout)
        main_layout.addStretch()

    def _on_mute(self, checked: bool):
        self.is_muted = checked
        if checked and self.is_soloed:
            self.btn_solo.setChecked(False)
        self.mute_toggled.emit(self.name, checked)

    def _on_solo(self, checked: bool):
        self.is_soloed = checked
        if checked and self.is_muted:
            self.btn_mute.setChecked(False)
        self.solo_toggled.emit(self.name, checked)

    def _on_vol(self, val: int):
        # 0 to 100 -> 0.0 to 1.25 linear gain
        gain = (val / 80.0)
        self.volume_changed.emit(self.name, gain)
