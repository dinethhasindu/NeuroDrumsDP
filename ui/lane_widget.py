from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QSlider
from PySide6.QtCore import Signal,Qt
from PySide6.QtGui import QColor

class LaneWidget(QWidget):
    mute_toggled=Signal(str,bool); solo_toggled=Signal(str,bool); volume_changed=Signal(str,float)
    def __init__(self,name,color,parent=None):
        super().__init__(parent); self.name=name; self.color=color; self.setFixedWidth(190); self.setFixedHeight(82)
        self.setStyleSheet(f'background:#12161b;border-bottom:1px solid #252b33;')
        lay=QVBoxLayout(self); lay.setContentsMargins(10,8,8,8); lay.setSpacing(5)
        top=QHBoxLayout(); lab=QLabel(name); lab.setStyleSheet(f'color:{color};font-weight:700;font-size:14px;'); top.addWidget(lab); top.addStretch()
        self.m=QPushButton('M'); self.s=QPushButton('S'); self.m.setFixedSize(24,22); self.s.setFixedSize(24,22)
        for b in (self.m,self.s): b.setCheckable(True); b.setStyleSheet('QPushButton{padding:0;font-size:11px;} QPushButton:checked{background:#394452;color:white;}')
        self.m.toggled.connect(lambda v:self.mute_toggled.emit(self.name,v)); self.s.toggled.connect(lambda v:self.solo_toggled.emit(self.name,v)); top.addWidget(self.m); top.addWidget(self.s); lay.addLayout(top)
        row=QHBoxLayout(); lab2=QLabel('VOL'); lab2.setStyleSheet('color:#667281;font-size:10px;'); row.addWidget(lab2)
        sl=QSlider(Qt.Horizontal); sl.setRange(0,100); sl.setValue(100); sl.valueChanged.connect(lambda v:self.volume_changed.emit(self.name,v/100)); row.addWidget(sl); lay.addLayout(row)
