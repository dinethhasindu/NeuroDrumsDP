"""
NeuroDrums AI - Sample Browser UI.
Left panel for browsing and dragging replacement samples.
"""
from __future__ import annotations
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTreeView, QFileSystemModel,
    QHeaderView, QPushButton, QHBoxLayout, QLineEdit
)
from PySide6.QtCore import Qt, QDir, Signal

class SampleBrowser(QWidget):
    """
    File browser restricted to the samples directory.
    Users can preview and drag samples to lanes.
    """
    
    sample_preview_requested = Signal(str) # Emits absolute path to sample

    def __init__(self, samples_dir: str = "samples", parent=None):
        super().__init__(parent)
        self.samples_dir = os.path.abspath(samples_dir)
        os.makedirs(self.samples_dir, exist_ok=True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header
        header = QLabel("Samples")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # File System Model
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self.model.setNameFilters(["*.wav", "*.mp3", "*.flac", "*.ogg"])
        self.model.setNameFilterDisables(False)
        self.model.setRootPath(self.samples_dir)

        # Tree View
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(self.samples_dir))
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(QTreeView.DragOnly)
        
        # Hide extra columns (size, type, date)
        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)
        self.tree.setHeaderHidden(True)
        
        self.tree.doubleClicked.connect(self._on_double_click)

        layout.addWidget(self.tree)

    def _on_double_click(self, index):
        if not self.model.isDir(index):
            path = self.model.filePath(index)
            self.sample_preview_requested.emit(path)
