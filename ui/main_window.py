import tkinter as tk
import os
from tkinterdnd2 import DND_FILES
from waveform.viewer import WaveformViewer
from audio.player import AudioPlayer
from ai.separator import DemucsSeparator
from ai.detector import DrumDetector

class NeuroDrumsUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NeuroDrums DP - AI Drum Replacer")
        self.root.geometry("1000x650")
        self.root.configure(bg="#1e1e1e")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.audio_player = AudioPlayer()
        self.ai_separator = DemucsSeparator()
        self.ai_detector = DrumDetector()

        self.setup_ui()

    def on_closing(self):
        print("Force closing application and all background AI tasks...")
        self.root.destroy()
        os._exit(0)

    def setup_ui(self):
        self.drop_frame = tk.Frame(self.root, bg="#2d2d2d", height=100)
        self.drop_frame.pack(fill=tk.X, padx=15, pady=15)
        self.drop_frame.pack_propagate(False)

        self.drop_label = tk.Label(self.drop_frame, text="Drop Audio Stem Here (.wav / .mp3)", bg="#2d2d2d", fg="#ffffff", font=("Segoe UI", 12))
        self.drop_label.pack(expand=True)

        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.handle_drop)

        self.wave_frame = tk.Frame(self.root, bg="#121212")
        self.wave_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        self.viewer = WaveformViewer(self.wave_frame)

        self.control_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.control_frame.pack(fill=tk.X, padx=15, pady=15)

        self.play_btn = tk.Button(self.control_frame, text="▶ Play Drums", bg="#4CAF50", fg="white", font=("Segoe UI", 10, "bold"), bd=0, padx=15, pady=5, command=self.play_audio)
        self.play_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(self.control_frame, text="■ Stop", bg="#F44336", fg="white", font=("Segoe UI", 10, "bold"), bd=0, padx=15, pady=5, command=self.stop_audio)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.gpu_var = tk.BooleanVar(value=True)
        self.gpu_check = tk.Checkbutton(self.control_frame, text="Use GPU Acceleration", variable=self.gpu_var, bg="#1e1e1e", fg="#FFC107", selectcolor="#2d2d2d", activebackground="#1e1e1e", activeforeground="#FFC107", font=("Segoe UI", 9, "bold"))
        self.gpu_check.pack(side=tk.LEFT, padx=15)

        self.status_var = tk.StringVar()
        self.status_var.set("Status: Ready")
        self.status_label = tk.Label(self.control_frame, textvariable=self.status_var, bg="#1e1e1e", fg="#00BCD4", font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def handle_drop(self, event):
        file_path = event.data.strip('{}') 
        filename = file_path.split('/')[-1].split('\\')[-1]
        
        self.status_var.set(f"Status: AI Processing (Separating Drums from {filename})...")
        self.drop_label.config(text="AI is processing... This might take a moment.", fg="#FFC107")
        self.root.update()

        use_gpu = self.gpu_var.get()
        self.ai_separator.separate(file_path, use_gpu, self.on_separation_complete)

    def on_separation_complete(self, success, result_path):
        self.root.after(0, self._update_ui_after_ai, success, result_path)

    def _update_ui_after_ai(self, success, result_path):
        if success:
            self.status_var.set("Status: AI Separation Complete. Classifying Drum Hits...")
            self.root.update()
            
            y_mono, sr = self.audio_player.load_file(result_path)
            
            if y_mono is not None:
                # අලුත් Function එක කෝල් කරනවා
                classified_hits = self.ai_detector.detect_and_classify(y_mono, sr)
                self.viewer.plot_waveform(y_mono, sr, classified_hits)
                
                # Kick, Snare, Hat ගාන වෙන වෙනම ගණන් කරනවා
                kicks = sum(1 for hit in classified_hits if hit["type"] == "Kick")
                snares = sum(1 for hit in classified_hits if hit["type"] == "Snare")
                hats = sum(1 for hit in classified_hits if hit["type"] == "Hat")
                
                self.status_var.set(f"Found: {kicks} Kicks | {snares} Snares | {hats} Hats")
                self.drop_label.config(text="Drop Audio Stem Here (.wav / .mp3)", fg="#ffffff")
            else:
                self.status_var.set("Status: Error Loading Separated Audio.")
        else:
            self.status_var.set(f"Status: AI Error - {result_path}")
            self.drop_label.config(text="Drop Audio Stem Here (.wav / .mp3)", fg="#ffffff")

    def play_audio(self):
        self.audio_player.play()
        self.status_var.set("Status: Playing Isolated Drums")

    def stop_audio(self):
        self.audio_player.stop()
        self.status_var.set("Status: Stopped")