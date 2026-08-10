DARK_THEME_QSS = r'''
QMainWindow,QWidget { background:#0b0d10; color:#e8edf3; font-family:"Segoe UI"; font-size:13px; }
QFrame#Header,QFrame#Card,QFrame#Panel { background:#11151a; border:1px solid #242a32; border-radius:10px; }
QLabel#Title { font-size:20px; font-weight:700; color:#f5f7fa; }
QLabel#Subtitle { color:#8e99a8; }
QLabel#Section { font-size:12px; font-weight:700; color:#8e99a8; letter-spacing:1px; }
QPushButton { background:#191f27; color:#dce3eb; border:1px solid #303843; border-radius:7px; padding:7px 12px; }
QPushButton:hover { background:#222a34; border-color:#475363; }
QPushButton:pressed { background:#12171d; }
QPushButton#accent { background:#2f81f7; border-color:#2f81f7; color:white; font-weight:600; }
QPushButton#accent:hover { background:#4b93f8; }
QPushButton#danger { color:#ff6b81; }
QLineEdit,QComboBox,QDoubleSpinBox,QSpinBox { background:#0d1116; border:1px solid #303843; border-radius:6px; padding:6px; color:#e8edf3; }
QSlider::groove:horizontal { height:4px; background:#303640; border-radius:2px; }
QSlider::handle:horizontal { width:12px; margin:-5px 0; border-radius:6px; background:#d8dee7; }
QScrollBar:horizontal,QScrollBar:vertical { background:#0b0d10; border:none; }
QScrollBar::handle:horizontal,QScrollBar::handle:vertical { background:#343b46; border-radius:5px; min-width:40px; min-height:40px; }
QProgressBar { background:#0b0d10; border:1px solid #2a3038; border-radius:5px; text-align:center; height:8px; }
QProgressBar::chunk { background:#2f81f7; border-radius:5px; }
QCheckBox { color:#b8c2cf; spacing:8px; }
'''
