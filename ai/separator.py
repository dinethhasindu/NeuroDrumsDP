import os
import subprocess
import threading

class DemucsSeparator:
    def __init__(self, output_dir="cache"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def separate(self, file_path, callback):
        # UI එක Freeze නොවී තියෙන්න AI process එක වෙනම Thread එකකින් run කරනවා
        thread = threading.Thread(target=self._run_demucs, args=(file_path, callback))
        thread.start()

    def _run_demucs(self, file_path, callback):
        try:
            # -n htdemucs_ft: Studio Quality Fine-tuned model එක
            # --shifts=2: Shift trick එකෙන් artifacts (පැහැදිලි නැති සද්ද) අයින් කරනවා
            command = [
                "demucs",
                "--two-stems=drums",
                "-n", "htdemucs_ft",
                "--shifts=2",
                "-o", self.output_dir,
                file_path
            ]
            
            # Windows වලදී කළු පාට CMD එකක් pop-up වෙන එක නවත්තන්න
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            subprocess.run(command, check=True, creationflags=creation_flags)
            
            # htdemucs_ft පාවිච්චි කරන නිසා ෆෝල්ඩර් එකේ නම htdemucs_ft වෙනවා
            filename = os.path.splitext(os.path.basename(file_path))[0]
            drums_path = os.path.join(self.output_dir, "htdemucs_ft", filename, "drums.wav")
            
            if os.path.exists(drums_path):
                callback(True, drums_path)
            else:
                callback(False, "Drum stem not found.")
                
        except Exception as e:
            callback(False, str(e))