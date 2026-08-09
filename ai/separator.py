import os
import subprocess
import threading
import torch

class DemucsSeparator:
    def __init__(self, output_dir="cache"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def separate(self, file_path, use_gpu, callback):
        # UI එකෙන් එන use_gpu (True/False) එක AI එකට යවනවා
        thread = threading.Thread(target=self._run_demucs, args=(file_path, use_gpu, callback), daemon=True)
        thread.start()

    def _run_demucs(self, file_path, use_gpu, callback):
        try:
            # User GPU ඉල්ලලා තියෙනවද සහ PC එකේ GPU එකක් තියෙනවද කියලා check කරනවා
            if use_gpu and torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
                
            print(f"[AI Engine] Requested GPU: {use_gpu} | Using hardware: {device.upper()}")

            command = [
                "demucs",
                "--two-stems=drums",
                "-n", "htdemucs_ft",
                "--shifts=2",
                "-d", device, 
                "-o", self.output_dir,
                file_path
            ]
            
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            subprocess.run(command, check=True, creationflags=creation_flags)
            
            filename = os.path.splitext(os.path.basename(file_path))[0]
            drums_path = os.path.join(self.output_dir, "htdemucs_ft", filename, "drums.wav")
            
            if os.path.exists(drums_path):
                callback(True, drums_path)
            else:
                callback(False, "Drum stem not found.")
                
        except Exception as e:
            callback(False, str(e))