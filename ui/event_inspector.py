from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QHBoxLayout,QPushButton,QDoubleSpinBox,QComboBox,QCheckBox,QGroupBox
from PySide6.QtCore import Signal
class EventInspector(QWidget):
    event_changed=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self.current_event=None; self.setMinimumWidth(270); self.setMaximumWidth(320)
        self.lay=QVBoxLayout(self); self.lay.setContentsMargins(14,14,14,14); self.lay.setSpacing(10); self._build_empty()
    def _clear(self):
        while self.lay.count():
            item=self.lay.takeAt(0); w=item.widget()
            if w: w.deleteLater()
    def _build_empty(self):
        self._clear(); a=QLabel('NO EVENT SELECTED'); a.setObjectName('Section'); self.lay.addWidget(a); b=QLabel('Click an event block to edit its timing, dynamics and replacement.'); b.setWordWrap(True); b.setStyleSheet('color:#697586;'); self.lay.addWidget(b); self.lay.addStretch()
    def set_event(self,e):
        self.current_event=e; self._clear()
        title=QLabel('SELECTED EVENT'); title.setObjectName('Section'); self.lay.addWidget(title)
        name=QLabel(e.type); name.setStyleSheet('font-size:20px;font-weight:700;'); self.lay.addWidget(name)
        self.lay.addWidget(QLabel(f'AI confidence  {e.confidence*100:.0f}%'))
        for label,attr,lo,hi,step in [('Time','start',0,99999,0.001),('Velocity','velocity',0,1,0.01),('Volume dB','volume_db',-24,12,0.5),('Pitch st','pitch',-12,12,0.5),('Punch','punch',0,1,0.01),('Decay ms','decay_ms',10,1000,10),('Speed','speed',0.5,2,0.05)]:
            row=QHBoxLayout(); row.addWidget(QLabel(label)); box=QDoubleSpinBox(); box.setRange(lo,hi); box.setSingleStep(step); box.setValue(float(getattr(e,attr))); row.addWidget(box); self.lay.addLayout(row)
            box.valueChanged.connect(lambda v,a=attr:self._change(a,v))
        buttons=QHBoxLayout(); mute=QPushButton('Mute'); remove=QPushButton('Remove'); remove.setObjectName('danger'); buttons.addWidget(mute); buttons.addWidget(remove); self.lay.addLayout(buttons)
        mute.clicked.connect(lambda: self._change('muted',not e.muted)); remove.clicked.connect(lambda: self._change('removed',True)); self.lay.addStretch()
    def _change(self,attr,val):
        if self.current_event is None:return
        setattr(self.current_event,attr,val)
        if attr=='start': self.current_event.end=self.current_event.start+self.current_event.duration
        self.event_changed.emit(self.current_event.id)
