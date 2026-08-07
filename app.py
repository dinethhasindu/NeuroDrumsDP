import sys
from tkinterdnd2 import TkinterDnD
from ui.main_window import NeuroDrumsUI

def main():
    # TkinterDnD.Tk() enables drag-and-drop functionality
    root = TkinterDnD.Tk()
    app = NeuroDrumsUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()