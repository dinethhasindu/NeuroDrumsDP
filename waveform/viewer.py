"""Compatibility shim: the application now uses ui.waveform_editor (PySide6)."""
from ui.waveform_editor import WaveformEditor as WaveformViewer
__all__ = ["WaveformViewer"]
