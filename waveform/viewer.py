import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np

class WaveformViewer:
    def __init__(self, parent_frame):
        self.parent = parent_frame

        # Setup Matplotlib Figure with Dark Theme
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(10, 3), dpi=100)
        self.fig.patch.set_facecolor('#121212')
        self.ax.set_facecolor('#121212')

        # Clean up axes for a modern look
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)

        # Initial Placeholder text
        self.placeholder = self.ax.text(0.5, 0.5, 'Drop Audio Stem Here to View Waveform', color='#555555', ha='center', va='center', transform=self.ax.transAxes)

        # Embed into Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def plot_waveform(self, y, sr):
        self.ax.clear()
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)

        # Optimization: Downsample if the file is too large so UI doesn't freeze
        max_points = 500000
        if len(y) > max_points:
            hop_length = len(y) // max_points
            y_plot = y[::hop_length]
        else:
            y_plot = y

        time = np.linspace(0, len(y)/sr, num=len(y_plot))

        # Plot with a nice primary color
        self.ax.plot(time, y_plot, color='#00BCD4', alpha=0.8, linewidth=0.5)
        self.ax.set_xlim([0, time[-1]])

        self.canvas.draw()