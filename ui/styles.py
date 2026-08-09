"""
NeuroDrums AI - UI Styles (QSS).
Dark theme definitions.
"""
from __future__ import annotations

# Custom colors for palette
BG_DARK = "#121212"
BG_PANEL = "#1e1e1e"
BG_LIGHT = "#2a2a2a"
ACCENT = "#3a86ff"
ACCENT_HOVER = "#4ea8de"
TEXT_MAIN = "#e0e0e0"
TEXT_DIM = "#888888"
BORDER = "#333333"

DARK_THEME_QSS = f"""
QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_MAIN};
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
}}

/* Main Panels */
QFrame#Panel {{
    background-color: {BG_PANEL};
    border-radius: 6px;
    border: 1px solid {BORDER};
}}

/* Buttons */
QPushButton {{
    background-color: {BG_LIGHT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 12px;
    color: {TEXT_MAIN};
}}
QPushButton:hover {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
}}
QPushButton:pressed {{
    background-color: {ACCENT_HOVER};
}}
QPushButton:disabled {{
    background-color: {BG_DARK};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
}}

/* Accent Button */
QPushButton.AccentButton {{
    background-color: {ACCENT};
    color: white;
    font-weight: bold;
    border: none;
}}
QPushButton.AccentButton:hover {{
    background-color: {ACCENT_HOVER};
}}

/* ScrollBars */
QScrollBar:vertical {{
    border: none;
    background: {BG_DARK};
    width: 12px;
    margin: 0px 0px 0px 0px;
}}
QScrollBar::handle:vertical {{
    background: {BG_LIGHT};
    min-height: 20px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_DIM};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    border: none;
    background: {BG_DARK};
    height: 12px;
    margin: 0px 0px 0px 0px;
}}
QScrollBar::handle:horizontal {{
    background: {BG_LIGHT};
    min-width: 20px;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_DIM};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Sliders */
QSlider::groove:horizontal {{
    border: 1px solid {BORDER};
    height: 6px;
    background: {BG_DARK};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {TEXT_MAIN};
    border: 1px solid {BORDER};
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT};
}}

/* LineEdits / SpinBoxes */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
    color: {TEXT_MAIN};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

/* GroupBox */
QGroupBox {{
    font-weight: bold;
    border: 1px solid {BORDER};
    border-radius: 4px;
    margin-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 3px;
    color: {TEXT_DIM};
}}

/* Tree/List Widget */
QTreeWidget, QListWidget {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}
"""
