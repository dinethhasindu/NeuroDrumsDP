# NeuroDrumsDP

AI-assisted drum stem replacement and event editor.

## What this build fixes

- Waveform is rendered immediately after audio loading, before AI analysis finishes.
- Multi-resolution waveform cache is validated against the current sample rate and sample count.
- Horizontal zoom/scroll is tied to the timeline and editor width.
- Eight synchronized lanes: Kick, Snare, Closed Hat, Open Hat, Clap, Roll, Snare Roll, FX.
- AI analysis runs in the background so the UI remains responsive.
- Drum-stem mode bypasses Demucs; full-song mode can use Demucs when installed.
- A trained `models/drum_rf_classifier.pkl` is used automatically when supplied. Without it, the app uses a multi-feature signal-classification fallback and labels the engine honestly.
- Event selection, drag timing, mute, lane mute/solo, sample replacement, project save/load and WAV export are included.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

For full-song separation, install a compatible PyTorch + Demucs environment separately. Drum-stem mode does not require Demucs.

## Samples

Put samples in:

- `samples/kick`
- `samples/snare`
- `samples/closed_hat`
- `samples/open_hat`
- `samples/clap`
- `samples/roll`
- `samples/snare_roll`
- `samples/fx`

## Project workflow

Load audio → waveform appears → AI detects events → review/correct → replace samples → preview/export.
