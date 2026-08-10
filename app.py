import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app=QApplication(sys.argv)
    app.setApplicationName('NeuroDrums AI')
    w=MainWindow(); w.show()
    return app.exec()

if __name__=='__main__': raise SystemExit(main())
