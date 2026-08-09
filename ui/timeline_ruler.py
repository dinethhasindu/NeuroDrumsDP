"""
NeuroDrums AI - Timeline Ruler Widget.
Displays time (seconds) and beat grid.
"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt

class TimelineRuler(QWidget):
    """
    Draws the timeline ruler at the top of the waveform editor.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.duration = 0.0
        self.zoom = 1.0
        self.scroll_x = 0
        self.content_offset = 0
        self.bpm = 120.0
        
    def update_state(
        self, duration: float, zoom: float, scroll_x: int, bpm: float, content_offset: int = 0
    ):
        self.duration = duration
        self.zoom = zoom
        self.scroll_x = scroll_x
        self.bpm = bpm
        self.content_offset = content_offset
        self.update()

    def paintEvent(self, event):
        if self.duration <= 0:
            return

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1a1a1a"))
        
        pen_text = QPen(QColor("#888888"))
        pen_tick = QPen(QColor("#444444"))
        
        w = self.width()
        
        # This ruler follows the editor's coordinate system: zoom is pixels
        # per second and scroll_x is the horizontal scroll-area offset.
        pps = self.zoom
        
        # Determine tick interval based on zoom
        if pps > 500:
            interval = 0.1
        elif pps > 100:
            interval = 0.5
        elif pps > 50:
            interval = 1.0
        elif pps > 10:
            interval = 5.0
        else:
            interval = 10.0
            
        start_t = max(0.0, (self.scroll_x - self.content_offset) / pps)
        end_t = max(0.0, (self.scroll_x + w - self.content_offset) / pps)
        
        # Draw time ticks
        t = (start_t // interval) * interval
        while t <= end_t:
            if t >= 0 and t <= self.duration:
                x = int(self.content_offset + t * pps) - self.scroll_x
                
                # Major tick
                if abs(t % (interval * 5)) < 1e-5:
                    painter.setPen(pen_text)
                    painter.drawLine(x, 16, x, 32)
                    painter.drawText(x + 2, 14, f"{t:.1f}s")
                else:
                    painter.setPen(pen_tick)
                    painter.drawLine(x, 24, x, 32)
                    
            t += interval

        painter.end()
