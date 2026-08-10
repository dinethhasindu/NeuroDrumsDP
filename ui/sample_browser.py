from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QTreeWidget,QTreeWidgetItem,QPushButton,QHBoxLayout
from PySide6.QtCore import Qt, QMimeData, QUrl
from PySide6.QtGui import QDrag
from PySide6.QtCore import QMimeData
import os
from core.constants import LANE_SAMPLE_DIRS

class SampleTree(QTreeWidget):
    def mimeData(self, items):
        md=QMimeData()
        urls=[]
        for item in items:
            p=item.data(0,Qt.UserRole)
            if p and os.path.isfile(p): urls.append(QUrl.fromLocalFile(p))
        md.setUrls(urls)
        return md

class SampleBrowser(QWidget):
    def __init__(self,root='samples',parent=None):
        super().__init__(parent); self.root=root; self.setMinimumWidth(190); self.setMaximumWidth(240)
        lay=QVBoxLayout(self); lay.setContentsMargins(10,10,10,10)
        title=QLabel('SAMPLE LIBRARY'); title.setObjectName('Section'); lay.addWidget(title)
        self.tree=SampleTree(); self.tree.setHeaderHidden(True); self.tree.setDragEnabled(True); self.tree.itemDoubleClicked.connect(self._preview); lay.addWidget(self.tree,1)
        hint=QLabel('Double-click to preview\nDrag a sample onto a lane'); hint.setStyleSheet('color:#667281;font-size:11px;'); lay.addWidget(hint)
        self._fill()
    def _fill(self):
        self.tree.clear(); os.makedirs(self.root,exist_ok=True)
        for lane,path in LANE_SAMPLE_DIRS.items():
            folder=QTreeWidgetItem([lane]); folder.setData(0,Qt.UserRole,path); self.tree.addTopLevelItem(folder)
            os.makedirs(path,exist_ok=True)
            for f in sorted(os.listdir(path)):
                if f.lower().endswith(('.wav','.mp3','.flac','.ogg','.m4a')):
                    item=QTreeWidgetItem([f]); item.setData(0,Qt.UserRole,os.path.abspath(os.path.join(path,f))); folder.addChild(item)
            folder.setExpanded(True)
    def _preview(self,item,col):
        p=item.data(0,Qt.UserRole)
        if p and os.path.isfile(p):
            try:
                import sounddevice as sd
                import soundfile as sf
                y,sr=sf.read(p,dtype='float32'); sd.stop(); sd.play(y,sr)
            except Exception: pass
    def startDrag(self, supportedActions):
        item=self.tree.currentItem(); p=item.data(0,Qt.UserRole) if item else None
        if not p or not os.path.isfile(p): return
        md=QMimeData(); md.setUrls([QUrl.fromLocalFile(p)])
        drag=QDrag(self.tree); drag.setMimeData(md); drag.exec(Qt.CopyAction)
