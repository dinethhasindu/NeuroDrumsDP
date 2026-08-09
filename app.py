"""
NeuroDrums AI - Application Entry Point.
Starts the PySide6 application.
"""
import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    # Make sure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    app = QApplication(sys.argv)
    app.setApplicationName("NeuroDrums AI")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()