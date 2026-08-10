from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter,QPen,QColor,QFont
from PySide6.QtCore import Qt
import math
class TimelineRuler(QWidget):
    def __init__(self,parent=None): super().__init__(parent); self.duration=0; self.zoom=120; self.offset=0; self.setFixedHeight(34)
    def set_state(self,duration,zoom,offset=0,bpm=120): self.duration=duration; self.zoom=zoom; self.offset=offset; self.update()
    def paintEvent(self,e):
        p=QPainter(self); p.fillRect(self.rect(),QColor('#0e1217')); p.setFont(QFont('Segoe UI',9));
        if self.duration<=0: return
        minor=max(0.25,1.0/self.zoom*90); major=max(1.0,minor*4); x=0.0
        while x<=self.width()/self.zoom+1:
            px=x*self.zoom; ismaj=abs((x/major)-round(x/major))<0.02
            p.setPen(QPen(QColor('#4b5563' if ismaj else '#2a3038'),1)); p.drawLine(int(px),34 if ismaj else 20,int(px),0)
            if ismaj: p.setPen(QColor('#9aa5b3')); p.drawText(int(px+4),15,f'{x:.1f}s')
            x+=minor
        p.end()
