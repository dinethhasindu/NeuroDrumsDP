import tkinter as tk
from tkinterdnd2 import DND_FILES
from waveform.viewer import WaveformViewer
from audio.player import AudioPlayer

class NeuroDrumsUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NeuroDrums DP - AI Drum Replacer")
        self.root.geometry("1000x650")
        self.root.configure(bg="#1e1e1e") # Modern Dark Background

        # Initialize core engines
        self.audio_player = AudioPlayer()

        self.setup_ui()

    def setup_ui(self):
        # 1. Drag & Drop Zone (Top)
        self.drop_frame = tk.Frame(self.root, bg="#2d2d2d", height=100)
        self.drop_frame.pack(fill=tk.X, padx=15, pady=15)
        self.drop_frame.pack_propagate(False)

        self.drop_label = tk.Label(self.drop_frame, text="Drop Audio Stem Here (.wav / .mp3)", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 12))
        self.drop_label.pack(expand=True)

        # Register Drop Target
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.handle_drop)

        # 2. Waveform Viewer Area (Middle)
        self.wave_frame = tk.Frame(self.root, bg="#121212")
        self.wave_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        self.viewer = WaveformViewer(self.wave_frame)

        # 3. Transport Controls & Status (Bottom)
        self.control_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.control_frame.pack(fill=tk.X, padx=15, pady=15)

        self.play_btn = tk.Button(self.control_frame, text="▶ Play", bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"), bd=0, padx=15, pady=5, command=self.play_audio)
        self.play_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(self.control_frame, text="■ Stop", bg="#F44336", fg="white", font=("Segoe UI", 10, "bold"), bd=0, padx=15, pady=5, command=self.stop_audio)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar()
        self.status_var.set("Status: Ready")
        self.status_label = tk.Label(self.control_frame, textvariable=self.status_var, bg="#1e1e1e", fg="#888888", font=("Segoe UI", 9))
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def handle_drop(self, event):
        # Clean path (Windows adds {} around paths with spaces)
        file_path = event.data.strip('{}') 
        self.status_var.set(f"Status: Loading {file_path.split('/')[-1]}...")
        self.root.update()

        # Load Audio to Player Engine
        y_mono, sr = self.audio_player.load_file(file_path)
        
        if y_mono is not None:
            # Send mono data to waveform viewer
            self.viewer.plot_waveform(y_mono, sr)
            self.status_var.set("Status: Audio Loaded. Ready for AI Analysis.")
        else:
            self.status_var.set("Status: Error Loading Audio File.")

    def play_audio(self):
        self.audio_player.play()
        self.status_var.set("Status: Playing")

    def stop_audio(self):
        self.audio_player.stop()
        self.status_var.set("Status: Stopped")