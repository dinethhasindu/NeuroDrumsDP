import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np

class WaveformViewer:
    def __init__(self, parent_frame):
        self.parent = parent_frame
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(10, 3), dpi=100)
        self.fig.patch.set_facecolor('#121212')
        self.ax.set_facecolor('#121212')

        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)

        self.placeholder = self.ax.text(0.5, 0.5, 'Drop Audio Stem Here to View Waveform', color='#555555', ha='center', va='center', transform=self.ax.transAxes)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def plot_waveform(self, y, sr, classified_hits=None):
        self.ax.clear()
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)

        max_points = 500000
        if len(y) > max_points:
            hop_length = len(y) // max_points
            y_plot = y[::hop_length]
        else:
            y_plot = y

        time = np.linspace(0, len(y)/sr, num=len(y_plot))

        # Waveform එක නිල් පාටින් අඳිනවා
        self.ax.plot(time, y_plot, color='#00BCD4', alpha=0.6, linewidth=0.5)
        
        # වර්ග කරපු Hits ටික අඳිනවා (Kick = Red, Snare = Blue, Hat = Yellow)
        if classified_hits is not None:
            for hit in classified_hits:
                if hit["type"] == "Kick":
                    color = '#FF5252' # Red
                elif hit["type"] == "Snare":
                    color = '#448AFF' # Blue
                else:
                    color = '#FFC107' # Yellow
                    
                self.ax.axvline(x=hit["time"], color=color, alpha=0.9, linestyle='-', linewidth=1.2)

        self.ax.set_xlim([0, time[-1]])
        self.canvas.draw()