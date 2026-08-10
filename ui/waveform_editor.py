from __future__ import annotations
import copy
import numpy as np
from PySide6.QtWidgets import QWidget, QMenu, QFileDialog
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QMouseEvent, QWheelEvent
from PySide6.QtCore import Qt, Signal, QRectF
from core.constants import LANE_NAMES, LANE_COLORS, LANE_HEIGHT, MIN_ZOOM, MAX_ZOOM


class OverviewWaveform(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cache = None
        self.duration = 0
        self.playhead = 0
        self.setMinimumHeight(86)
        self.setStyleSheet('background:#0e1217;')

    def set_data(self, cache, duration):
        self.cache = cache
        self.duration = duration
        self.update()

    def set_playhead(self, p):
        self.playhead = p
        self.update()

    def mousePressEvent(self, e):
        if self.duration and e.button() == Qt.LeftButton:
            self.seek_requested.emit(max(0, min(self.duration, e.position().x() / max(1, self.width()) * self.duration)))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#0e1217'))
        p.setPen(QPen(QColor('#252c35')))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if not self.cache or self.duration <= 0:
            return
        times, mn, mx = self.cache.get_peaks(0, self.duration, max(2, self.width()), self.width() / self.duration)
        if len(times):
            path = QPainterPath()
            center = self.height() / 2
            scale = self.height() * 0.42
            for i, (t, a, b) in enumerate(zip(times, mn, mx)):
                x = t / self.duration * self.width()
                y1 = center - b * scale
                if i == 0:
                    path.moveTo(x, y1)
                else:
                    path.lineTo(x, y1)
            for t, a, b in zip(times[::-1], mn[::-1], mx[::-1]):
                path.lineTo(t / self.duration * self.width(), center - a * scale)
            path.closeSubpath()
            p.setBrush(QBrush(QColor('#2f81f7')))
            p.setPen(Qt.NoPen)
            p.drawPath(path)
            p.setPen(QPen(QColor('#7fb3ff'), 1))
            p.drawLine(0, int(center), self.width(), int(center))
        x = self.playhead / self.duration * self.width()
        p.setPen(QPen(QColor('#ff4d6d'), 2))
        p.drawLine(int(x), 0, int(x), self.height())
        p.end()


class WaveformEditor(QWidget):
    event_selected = Signal(str)
    events_moved = Signal(list, list, list)
    seek_requested = Signal(float)
    sample_dropped = Signal(str, str)
    zoom_changed = Signal(float)
    events_deleted = Signal(list)
    events_duplicated = Signal(list)
    events_bulk_modified = Signal(dict, dict)
    split_requested = Signal(str, float)
    replace_sample_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.events = []
        self.cache = None
        self.duration = 0.0
        self.zoom = 120.0
        self.playhead = 0.0
        self.selected = set()
        self.hover = None
        self.drag = None
        self.rubber_band = None
        self.clipboard = []
        self.snap_enabled = False
        self.grid_fraction = 1 / 4
        self.triplet_grid = False
        self.bpm = 120.0
        self.drag_mode = None

    def set_data(self, events, cache, duration, zoom=None, bpm=120.0):
        self.events = events or []
        self.cache = cache
        self.duration = float(duration)
        self.zoom = float(zoom or self.zoom)
        self.bpm = bpm
        self._resize()
        self.update()

    def set_snap(self, enabled, fraction, triplet=False):
        self.snap_enabled = enabled
        self.grid_fraction = fraction
        self.triplet_grid = triplet
        self.update()

    def _get_snap_time(self, t):
        if not self.snap_enabled or self.bpm <= 0:
            return t
        beat_dur = 60.0 / self.bpm
        step = beat_dur * (self.grid_fraction * 4)
        if self.triplet_grid:
            step *= 2 / 3
        return round(t / step) * step

    def _resize(self):
        self.setMinimumWidth(max(900, int(self.duration * self.zoom) + 20))
        self.setMinimumHeight(len(LANE_NAMES) * LANE_HEIGHT)

    def set_zoom(self, z):
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, float(z)))
        self._resize()
        self.zoom_changed.emit(self.zoom)
        self.update()

    def set_playhead(self, p):
        self.playhead = max(0, min(self.duration, float(p)))
        self.update()

    def _lane_at(self, y):
        idx = int(y // LANE_HEIGHT)
        return LANE_NAMES[idx] if 0 <= idx < len(LANE_NAMES) else None

    def _event_at(self, x, y):
        lane = self._lane_at(y)
        t = x / self.zoom
        if not lane:
            return None
        hits = [
            e for e in self.events
            if not e.removed and e.type == lane and e.start - 0.015 <= t <= max(e.end, e.start + 0.045)
        ]
        return min(hits, key=lambda e: abs(e.start - t)) if hits else None

    def _hit_test_handles(self, ev, x, y):
        x1 = ev.start * self.zoom
        x2 = max(x1 + 6, ev.end * self.zoom)
        li = LANE_NAMES.index(ev.type)
        y1 = li * LANE_HEIGHT + 10
        h = LANE_HEIGHT - 20
        if y < y1 + 12:
            if abs(x - x1) < 10:
                return 'fade_in'
            if abs(x - x2) < 10:
                return 'fade_out'
        if abs(x - x1) < 6 and y1 <= y <= y1 + h:
            return 'trim_start'
        if abs(x - x2) < 6 and y1 <= y <= y1 + h:
            return 'trim_end'
        return None

    def _state_snapshot(self, ev):
        return {
            'start': ev.start, 'end': ev.end, 'duration': ev.duration,
            'timing_offset_ms': getattr(ev, 'timing_offset_ms', 0),
            'source_offset_ms': getattr(ev, 'source_offset_ms', 0),
            'fade_in_ms': ev.fade_in_ms, 'fade_out_ms': ev.fade_out_ms,
        }

    def mousePressEvent(self, e: QMouseEvent):
        x, y = float(e.position().x()), float(e.position().y())
        if e.button() == Qt.RightButton:
            ev = self._event_at(x, y)
            if ev and ev.id not in self.selected:
                self.selected = {ev.id}
            self.update()
            return

        if e.button() != Qt.LeftButton:
            return

        ev = self._event_at(x, y)
        if ev:
            if e.modifiers() & Qt.ShiftModifier:
                if ev.id in self.selected:
                    self.selected.remove(ev.id)
                else:
                    self.selected.add(ev.id)
            elif ev.id not in self.selected:
                self.selected = {ev.id}

            if len(self.selected) == 1:
                self.event_selected.emit(list(self.selected)[0])
            else:
                self.event_selected.emit('')

            hm = self._hit_test_handles(ev, x, y) if len(self.selected) == 1 else None
            if hm:
                self.drag_mode = hm
                self.drag = (x, {ev.id: self._state_snapshot(ev)})
            else:
                self.drag_mode = 'move'
                self.drag = (
                    x,
                    {e2.id: {'start': e2.start, 'end': e2.end} for e2 in self.events if e2.id in self.selected},
                )
        else:
            self.selected.clear()
            self.event_selected.emit('')
            if e.modifiers() & Qt.ShiftModifier:
                self.drag_mode = 'select'
                self.rubber_band = (x, y, x, y)
            else:
                self.seek_requested.emit(self._get_snap_time(max(0, min(self.duration, x / self.zoom))))
        self.update()

    def mouseMoveEvent(self, e):
        x, y = float(e.position().x()), float(e.position().y())
        ev = self._event_at(x, y)
        self.hover = ev.id if ev else None

        if self.drag_mode == 'select' and self.rubber_band:
            self.rubber_band = (self.rubber_band[0], self.rubber_band[1], x, y)
            self.update()
            return

        if self.drag:
            dx = x - self.drag[0]
            dt = dx / self.zoom
            for obj in self.events:
                if obj.id not in self.drag[1]:
                    continue
                orig = self.drag[1][obj.id]
                if self.drag_mode == 'move':
                    new_t = orig['start'] + dt
                    if self.snap_enabled:
                        new_t = self._get_snap_time(new_t)
                    obj.start = max(0, min(self.duration - obj.duration, new_t))
                    obj.end = obj.start + obj.duration
                elif self.drag_mode == 'fade_in':
                    obj.fade_in_ms = max(0.0, min(obj.duration * 1000, orig['fade_in_ms'] + dt * 1000))
                elif self.drag_mode == 'fade_out':
                    obj.fade_out_ms = max(0.0, min(obj.duration * 1000, orig['fade_out_ms'] - dt * 1000))
                elif self.drag_mode == 'trim_start':
                    new_start = orig['start'] + dt
                    if self.snap_enabled:
                        new_start = self._get_snap_time(new_start)
                    new_start = min(new_start, obj.end - 0.01)
                    dt_actual = new_start - orig['start']
                    obj.start = max(0, new_start)
                    obj.duration = obj.end - obj.start
                    obj.source_offset_ms = orig.get('source_offset_ms', 0) + dt_actual * 1000
                elif self.drag_mode == 'trim_end':
                    new_end = orig['end'] + dt
                    if self.snap_enabled:
                        new_end = self._get_snap_time(new_end)
                    new_end = max(new_end, obj.start + 0.01)
                    obj.end = min(self.duration, new_end)
                    obj.duration = obj.end - obj.start
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.drag_mode == 'select' and self.rubber_band:
                rx1, ry1, rx2, ry2 = self.rubber_band
                rx1, rx2 = min(rx1, rx2), max(rx1, rx2)
                ry1, ry2 = min(ry1, ry2), max(ry1, ry2)
                for ev in self.events:
                    if ev.removed:
                        continue
                    ex1 = ev.start * self.zoom
                    ex2 = ev.end * self.zoom
                    ey1 = LANE_NAMES.index(ev.type) * LANE_HEIGHT
                    ey2 = ey1 + LANE_HEIGHT
                    if ex2 >= rx1 and ex1 <= rx2 and ey2 >= ry1 and ey1 <= ry2:
                        self.selected.add(ev.id)
                self.rubber_band = None
            elif self.drag and self.selected:
                if self.drag_mode == 'move':
                    ids = list(self.selected)
                    old_starts = [self.drag[1][eid]['start'] for eid in ids]
                    new_starts = []
                    for eid in ids:
                        for ev in self.events:
                            if ev.id == eid:
                                new_starts.append(ev.start)
                                break
                    self.events_moved.emit(ids, new_starts, old_starts)
                elif self.drag_mode in ('fade_in', 'fade_out', 'trim_start', 'trim_end'):
                    old_states = self.drag[1]
                    new_states = {ev.id: self._state_snapshot(ev) for ev in self.events if ev.id in old_states}
                    self.events_bulk_modified.emit(old_states, new_states)
                    if len(self.selected) == 1:
                        self.event_selected.emit(list(self.selected)[0])
            self.drag = None
            self.drag_mode = None
            self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete and self.selected:
            self.events_deleted.emit(list(self.selected))
        elif e.key() == Qt.Key_D and (e.modifiers() & Qt.ControlModifier) and self.selected:
            self.events_duplicated.emit(list(self.selected))
        elif e.key() == Qt.Key_C and (e.modifiers() & Qt.ControlModifier) and self.selected:
            self.copy_selection()
        elif e.key() == Qt.Key_X and (e.modifiers() & Qt.ControlModifier) and self.selected:
            self.copy_selection()
            self.events_deleted.emit(list(self.selected))
        elif e.key() == Qt.Key_V and (e.modifiers() & Qt.ControlModifier):
            self.paste_at_playhead()
        else:
            super().keyPressEvent(e)

    def copy_selection(self):
        self.clipboard = [copy.deepcopy(e) for e in self.events if e.id in self.selected]

    def paste_at_playhead(self):
        return self.clipboard, self.playhead, self._lane_at(self.height() / 2)

    def contextMenuEvent(self, e):
        x, y = e.pos().x(), e.pos().y()
        ev = self._event_at(x, y)
        menu = QMenu(self)
        if ev or self.selected:
            menu.addAction('Copy', lambda: self.copy_selection())
            menu.addAction('Paste', lambda: self.paste_at_playhead())
            menu.addAction('Duplicate', lambda: self.events_duplicated.emit(list(self.selected)))
            menu.addAction('Delete', lambda: self.events_deleted.emit(list(self.selected)))
            menu.addSeparator()
            if len(self.selected) == 1:
                eid = list(self.selected)[0]
                menu.addAction('Split Here', lambda: self.split_requested.emit(eid, self.playhead))
                menu.addAction('Replace Sample…', lambda: self._pick_replacement(eid))
        menu.exec_(e.globalPos())

    def _pick_replacement(self, eid):
        path, _ = QFileDialog.getOpenFileName(self, 'Replace Sample', '', 'Audio (*.wav *.flac *.ogg *.mp3)')
        if path:
            self.replace_sample_requested.emit(eid, path)

    def wheelEvent(self, e: QWheelEvent):
        if e.modifiers() & Qt.ControlModifier:
            old = self.zoom
            factor = 1.18 if e.angleDelta().y() > 0 else 1 / 1.18
            self.set_zoom(old * factor)
            e.accept()
            return
        super().wheelEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        lane = self._lane_at(float(e.position().y()))
        if urls and lane:
            p = urls[0].toLocalFile()
            if p.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
                self.sample_dropped.emit(lane, p)
                e.acceptProposedAction()
                return
        e.ignore()

    def _draw_fade_curve(self, p, x1, x2, y, h, fade_in_ms, fade_out_ms, color):
        fi = min(x2 - x1, (fade_in_ms / 1000.0) * self.zoom)
        fo = min(x2 - x1, (fade_out_ms / 1000.0) * self.zoom)
        path = QPainterPath()
        path.moveTo(x1, y + h)
        path.lineTo(x1, y + h * 0.15)
        if fi > 2:
            path.lineTo(x1 + fi, y + h * 0.15)
        else:
            path.lineTo(x1 + 2, y + h * 0.15)
        path.lineTo(x2 - fo if fo > 2 else x2 - 2, y + h * 0.15)
        path.lineTo(x2, y + h * 0.15)
        path.lineTo(x2, y + h)
        path.closeSubpath()
        p.setPen(QPen(color, 1))
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 40))
        p.drawPath(path)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#0d1116'))
        if not self.cache or self.duration <= 0:
            return

        t0 = 0
        t1 = min(self.duration, self.width() / self.zoom)
        times, mn, mx = self.cache.get_peaks(t0, t1, max(100, self.width()), self.zoom)

        if self.snap_enabled and self.bpm > 0:
            p.setPen(QPen(QColor(255, 255, 255, 10), 1))
            beat_dur = 60.0 / self.bpm
            step = beat_dur * (self.grid_fraction * 4)
            if self.triplet_grid:
                step *= 2 / 3
            gt = 0
            while gt <= self.duration:
                gx = gt * self.zoom
                if 0 <= gx <= self.width():
                    p.drawLine(int(gx), 0, int(gx), self.height())
                gt += step

        for i, lane in enumerate(LANE_NAMES):
            y = i * LANE_HEIGHT
            bg = QColor('#11161c' if i % 2 == 0 else '#151a20')
            p.fillRect(0, y, self.width(), LANE_HEIGHT, bg)
            p.setPen(QPen(QColor('#252c34'), 1))
            p.drawLine(0, y + LANE_HEIGHT - 1, self.width(), y + LANE_HEIGHT - 1)
            p.setPen(QPen(QColor(LANE_COLORS[lane]), 1, Qt.DotLine))
            p.setOpacity(0.25)
            p.drawLine(0, y + LANE_HEIGHT / 2, self.width(), y + LANE_HEIGHT / 2)
            p.setOpacity(1)

        if len(times):
            for i, lane in enumerate(LANE_NAMES):
                center = i * LANE_HEIGHT + LANE_HEIGHT / 2
                scale = LANE_HEIGHT * 0.39
                p.setPen(QPen(QColor(LANE_COLORS[lane]), 1))
                p.setOpacity(0.22)
                stride = max(1, len(times) // max(1, self.width() // 2))
                for j in range(0, len(times), stride):
                    x = times[j] * self.zoom
                    p.drawLine(int(x), int(center - mx[j] * scale), int(x), int(center - mn[j] * scale))
                p.setOpacity(1)

        for ev in self.events:
            if ev.removed or ev.start > t1 or ev.end < t0 or ev.type not in LANE_NAMES:
                continue
            li = LANE_NAMES.index(ev.type)
            x1 = ev.start * self.zoom
            x2 = max(x1 + 6, ev.end * self.zoom)
            y = li * LANE_HEIGHT + 10
            h = LANE_HEIGHT - 20
            c = QColor(LANE_COLORS[ev.type])
            if ev.muted:
                c.setAlpha(90)
            elif ev.uncertain:
                c.setAlpha(160)
            else:
                c.setAlpha(180 if ev.uncertain else 230)
            is_sel = ev.id in self.selected
            if is_sel:
                c = c.lighter(135)

            if is_sel:
                self._draw_fade_curve(p, x1, x2, y, h, ev.fade_in_ms, ev.fade_out_ms, c)

            p.setBrush(QBrush(c))
            p.setPen(QPen(QColor('#ffffff') if is_sel else c.lighter(115), 2 if is_sel else 1))
            p.drawRoundedRect(QRectF(x1, y, x2 - x1, h), 5, 5)

            if is_sel:
                p.setBrush(QColor(255, 255, 255, 220))
                p.setPen(Qt.NoPen)
                fx1 = x1 + (ev.fade_in_ms / 1000) * self.zoom
                fx2 = x2 - (ev.fade_out_ms / 1000) * self.zoom
                p.drawPolygon([Qt.QPointF(x1, y), Qt.QPointF(fx1, y), Qt.QPointF(x1, y + 10)])
                p.drawPolygon([Qt.QPointF(x2, y), Qt.QPointF(fx2, y), Qt.QPointF(x2, y + 10)])
                p.setPen(QPen(QColor('#ffffff'), 2))
                p.drawLine(int(x1), int(y + h / 2), int(x1), int(y + h))
                p.drawLine(int(x2), int(y + h / 2), int(x2), int(y + h))

            label = ev.type
            if ev.replacement_sample:
                label += ' ●'
            p.setPen(QColor('#ffffff'))
            p.drawText(QRectF(x1 + 5, y + 18, max(20, x2 - x1 - 8), 18), Qt.AlignLeft, label)
            if ev.uncertain:
                p.setPen(QColor('#fbbf24'))
                p.drawText(QRectF(x2 - 16, y + 2, 14, 14), Qt.AlignRight, '⚠')
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 80))
            p.drawRect(QRectF(x1, y + LANE_HEIGHT - 29, max(3, (x2 - x1) * ev.confidence), 3))

        if self.rubber_band:
            rx1, ry1, rx2, ry2 = self.rubber_band
            p.setPen(QPen(QColor(100, 150, 255, 200), 1, Qt.DashLine))
            p.setBrush(QColor(100, 150, 255, 50))
            p.drawRect(QRectF(rx1, ry1, rx2 - rx1, ry2 - ry1))

        x = self.playhead * self.zoom
        p.setPen(QPen(QColor('#ff335f'), 2))
        p.drawLine(int(x), 0, int(x), self.height())
        p.setBrush(QColor('#ff335f'))
        p.drawEllipse(int(x) - 4, 2, 8, 8)
        p.end()
