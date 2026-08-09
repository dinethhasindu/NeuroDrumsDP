import os, subprocess, threading

class DemucsSeparator:
    def __init__(self, output_dir="cache"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def separate(self, file_path, use_gpu=True, callback=None):
        threading.Thread(target=self._run, args=(file_path,use_gpu,callback), daemon=True).start()

    def _run(self, file_path, use_gpu, callback):
        try:
            import torch
            device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
            cmd = ["demucs", "--two-stems=drums", "-n", "htdemucs_ft",
                   "--shifts=2", "-d", device, "-o", self.output_dir, file_path]
            flags = subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
            subprocess.run(cmd, check=True, creationflags=flags)
            name = os.path.splitext(os.path.basename(file_path))[0]
            path = os.path.join(self.output_dir, "htdemucs_ft", name, "drums.wav")
            if not os.path.exists(path):
                raise FileNotFoundError("Demucs finished but drums.wav was not found.")
            if callback: callback(True, path)
        except Exception as e:
            if callback: callback(False, str(e))
