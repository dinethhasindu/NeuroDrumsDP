"""
NeuroDrums AI - Waveform Editor.
Custom QWidget that draws the multi-track drum lanes using QPainter.
Handles scrolling, zooming, selection, and drag-and-drop.
"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QWheelEvent, QPainterPath
from PySide6.QtCore import Qt, Signal, QRectF

from core.models import DrumEvent
from core.constants import LANE_NAMES, LANE_COLORS, LANE_HEIGHT
from audio.waveform_cache import WaveformCache

class WaveformEditor(QWidget):
    """
    Renders the waveform peaks and drum events.
    """
    
    event_selected = Signal(str) # Emits event ID
    event_moved = Signal(str, float) # Emits (event_id, new_start_time)
    seek_requested = Signal(float)
    sample_dropped = Signal(str, str)  # Emits (lane_name, absolute_sample_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        
        self.events = []
        self.cache = None
        self.duration = 0.0
        
        self.zoom = 100.0 # pixels per second
        # The widget lives inside a QScrollArea, which already translates its
        # coordinate system.  Keep this for compatibility with callers, but
        # do not apply it a second time while painting or hit-testing.
        self.scroll_x = 0
        
        self.selected_event_id = None
        self.hovered_event_id = None
        
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_time = 0.0
        
        self.playhead_pos = 0.0
        
    def set_data(self, events, cache, duration):
        self.events = events
        self.cache = cache
        self.duration = duration
        self.update()
        
    def set_playhead(self, pos: float):
        self.playhead_pos = pos
        # Auto-scroll if playing and out of view
        # Not implementing full smooth auto-scroll here to keep it simple, but we trigger a repaint.
        self.update()

    def get_event_at_pos(self, x: int, y: int) -> DrumEvent | None:
        if not self.events:
            return None
            
        lane_idx = y // LANE_HEIGHT
        if lane_idx < 0 or lane_idx >= len(LANE_NAMES):
            return None
            
        lane_name = LANE_NAMES[lane_idx]
        t = x / self.zoom
        
        # Find event in this lane near time t
        # Events have a duration, or we click within a small window
        for e in self.events:
            if e.type == lane_name and not e.removed:
                if e.start <= t <= e.end:
                    return e
                    
        return None

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            event = self.get_event_at_pos(e.position().x(), e.position().y())
            if event:
                self.selected_event_id = event.id
                self.event_selected.emit(event.id)
                self._is_dragging = True
                self._drag_start_x = e.position().x()
                self._drag_start_time = event.start
            else:
                self.selected_event_id = None
                self.event_selected.emit("")
                seek_time = max(0.0, min(e.position().x() / self.zoom, self.duration))
                self.seek_requested.emit(seek_time)
            self.update()

    def mouseMoveEvent(self, e: QMouseEvent):
        event = self.get_event_at_pos(e.position().x(), e.position().y())
        hover_id = event.id if event else None
        
        if hover_id != self.hovered_event_id:
            self.hovered_event_id = hover_id
            self.update()
            
        if self._is_dragging and self.selected_event_id:
            dx = e.position().x() - self._drag_start_x
            dt = dx / self.zoom
            new_time = max(0.0, self._drag_start_time + dt)
            
            # Find the event and update its start (preview)
            for ev in self.events:
                if ev.id == self.selected_event_id:
                    ev.start = new_time
                    ev.end = new_time + ev.duration
                    break
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            if self.selected_event_id:
                for ev in self.events:
                    if ev.id == self.selected_event_id:
                        self.event_moved.emit(ev.id, ev.start)
                        break

    def wheelEvent(self, e: QWheelEvent):
        # Vertical scroll
        if e.angleDelta().y() != 0:
            pass # The parent QScrollArea handles vertical scroll

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        lane_idx = int(event.position().y()) // LANE_HEIGHT
        if 0 <= lane_idx < len(LANE_NAMES):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        lane_idx = int(event.position().y()) // LANE_HEIGHT
        urls = event.mimeData().urls()
        if not (0 <= lane_idx < len(LANE_NAMES)) or not urls:
            event.ignore()
            return

        path = urls[0].toLocalFile()
        if path.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a")):
            self.sample_dropped.emit(LANE_NAMES[lane_idx], path)
            event.acceptProposedAction()
        else:
            event.ignore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Background
        painter.fillRect(self.rect(), QColor("#121212"))
        
        if not self.cache or self.duration == 0:
            painter.end()
            return
            
        t_start = 0.0
        t_end = w / self.zoom
        
        # Draw lane backgrounds and grid
        for i, lane in enumerate(LANE_NAMES):
            y_offset = i * LANE_HEIGHT
            
            # Alt bg
            if i % 2 == 1:
                painter.fillRect(0, y_offset, w, LANE_HEIGHT, QColor("#1a1a1a"))
                
            # Separator
            painter.setPen(QPen(QColor("#333333")))
            painter.drawLine(0, y_offset + LANE_HEIGHT, w, y_offset + LANE_HEIGHT)
            
        # Draw waveform peaks for the visible region
        times, min_p, max_p = self.cache.get_peaks(t_start, t_end, w, self.zoom)
        if len(times) > 0:
            # We draw the same waveform faint in all lanes
            path = QPainterPath()
            
            # Convert times to x coordinates
            x_coords = times * self.zoom
            
            for i, lane in enumerate(LANE_NAMES):
                y_center = i * LANE_HEIGHT + (LANE_HEIGHT / 2)
                
                # Faint waveform
                painter.setPen(QPen(QColor("#444444")))
                for j in range(len(x_coords)):
                    x = x_coords[j]
                    y1 = y_center + (min_p[j] * (LANE_HEIGHT / 2.2))
                    y2 = y_center + (max_p[j] * (LANE_HEIGHT / 2.2))
                    painter.drawLine(x, y1, x, y2)

        # Draw Events
        for e in self.events:
            if e.removed or e.start > t_end or e.end < t_start:
                continue
                
            try:
                lane_idx = LANE_NAMES.index(e.type)
            except ValueError:
                continue
                
            y_offset = lane_idx * LANE_HEIGHT
            
            x1 = e.start * self.zoom
            x2 = e.end * self.zoom
            
            rect = QRectF(x1, y_offset + 5, max(4, x2 - x1), LANE_HEIGHT - 10)
            
            color = QColor(LANE_COLORS.get(e.type, "#ffffff"))
            if e.muted:
                color = QColor("#555555")
            elif e.uncertain:
                color.setAlpha(150)
                
            is_selected = (e.id == self.selected_event_id)
            is_hovered = (e.id == self.hovered_event_id)
            
            if is_selected:
                painter.setBrush(QBrush(color.lighter(130)))
                painter.setPen(QPen(QColor("#ffffff"), 2))
            elif is_hovered:
                painter.setBrush(QBrush(color.lighter(110)))
                painter.setPen(QPen(color, 1))
            else:
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                
            painter.drawRoundedRect(rect, 3, 3)
            
            # Velocity indicator (line)
            painter.setPen(QPen(QColor("#000000"), 1))
            v_y = y_offset + 5 + (LANE_HEIGHT - 10) * (1.0 - e.velocity)
            painter.drawLine(x1, v_y, x1 + rect.width(), v_y)

        # Draw Playhead
        ph_x = self.playhead_pos * self.zoom
        if 0 <= ph_x <= w:
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.drawLine(ph_x, 0, ph_x, h)
            
            # Playhead triangle
            path = QPainterPath()
            path.moveTo(ph_x - 5, 0)
            path.lineTo(ph_x + 5, 0)
            path.lineTo(ph_x, 8)
            path.closeSubpath()
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawPath(path)

        painter.end()
