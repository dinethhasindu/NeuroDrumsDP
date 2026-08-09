# NeuroDrums Pro

A local-first drum stem replacement editor.

## What this version does
- Drag/drop WAV/MP3 drum stem.
- Full timeline waveform with time ruler.
- 8 editable lanes: Kick, Snare, Closed Hat, Open Hat, Clap, Roll, Snare Roll, FX.
- Click to seek; moving playhead while playing.
- Horizontal zoom and scroll.
- Lane mute/solo.
- Select, delete, add events.
- Drop a WAV sample onto a lane.
- Replace selected hits or an entire lane.
- Volume, pitch, punch, decay and speed controls.
- Render/export WAV.
- AI pipeline hooks: Demucs for drum extraction and optional DrumSep ONNX for kick/snare/cymbal/tom separation.
- Conservative fallback detector if the ONNX model is not installed.

## Start
```powershell
python -m pip install -r requirements.txt
python app.py
```

## Optional AI model
Run:
```powershell
python models/download_models.py
```
This downloads the MIT-licensed DrumSep ONNX model (~335 MB) from Hugging Face.
