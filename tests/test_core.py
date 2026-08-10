import copy
import numpy as np
import pytest
from core.models import DrumEvent, ProjectState
from core.commands import (
    MoveEventsCommand, DeleteEventsCommand, SplitEventsCommand,
    PasteEventsCommand, BulkModifyCommand,
)
from project.manager import new_project, save_project, load_project
from detection.onset import detect_onsets, detect_bpm
from detection.transient import extract_features, feature_vector
from detection.roll import group_rolls
from ai.classifier import DrumClassifier
from audio.renderer import AudioRenderer
from audio.loader import load_audio
from audio.waveform_cache import WaveformCache


def _click():
    import librosa
    sr = 44100
    y = librosa.clicks(times=[0.05, 0.25], length=int(sr * 0.5), sr=sr).astype(np.float32)
    return y, sr


def test_onset_detection_finds_transients():
    y, sr = _click()
    times, strengths = detect_onsets(y, sr, 'high')
    assert len(times) >= 1
    assert len(strengths) == len(times)


def test_feature_extraction():
    y, sr = _click()
    f = extract_features(y, sr, 0.05)
    assert 'spectral_flux' in f
    assert 'attack_frac' in f
    assert f['rms'] > 0
    vec = feature_vector(f)
    assert vec.shape[0] >= 16


def test_classifier_fallback():
    clf = DrumClassifier(model_path='nonexistent.pkl')
    assert clf.mode == 'Analysis Fallback'
    assert clf.model_name == 'None'
    f = extract_features(*_click(), 0.05)
    typ, conf, _ = clf.classify(f)
    assert typ in ['Kick', 'Snare', 'Closed Hat', 'Open Hat', 'Clap', 'Roll', 'Snare Roll', 'FX']
    assert 0 <= conf <= 1


def test_roll_grouping():
    events = []
    for i in range(4):
        events.append(DrumEvent(type='Snare', start=0.1 * i, end=0.1 * i + 0.05, duration=0.05))
    grouped = group_rolls(events)
    assert any(e.type == 'Snare Roll' for e in grouped)


def test_move_events_command():
    p = new_project()
    e = DrumEvent(type='Kick', start=0.5, end=0.58, duration=0.08)
    p.events = [e]
    cb_called = []
    cmd = MoveEventsCommand(p, [e.id], [1.0], [0.5], lambda: cb_called.append(1))
    cmd.execute()
    assert p.events[0].start == 1.0
    cmd.undo()
    assert p.events[0].start == 0.5


def test_split_events_command():
    p = new_project()
    e = DrumEvent(type='Kick', start=0.0, end=1.0, duration=1.0)
    p.events = [e]
    cmd = SplitEventsCommand(p, e.id, 0.5, lambda: None)
    cmd.execute()
    assert len(p.events) == 2
    assert abs(sum(ev.duration for ev in p.events) - 1.0) < 1e-6


def test_bulk_modify_fade():
    p = new_project()
    e = DrumEvent(type='Kick', start=0.0, end=0.1, duration=0.1, fade_in_ms=2)
    p.events = [e]
    old = {e.id: {'fade_in_ms': 2.0}}
    new = {e.id: {'fade_in_ms': 50.0}}
    BulkModifyCommand(p, old, new, lambda: None).execute()
    assert p.events[0].fade_in_ms == 50.0


def test_renderer_applies_fade_and_replacement(tmp_path):
    y, sr = _click()
    full = np.zeros(sr * 2, dtype=np.float32)
    full[: len(y)] = y
    sample_path = tmp_path / 'kick.wav'
    import soundfile as sf
    sf.write(str(sample_path), y, sr)
    ev = DrumEvent(
        type='Kick', start=0.0, end=0.2, duration=0.2,
        replacement_sample=str(sample_path), fade_in_ms=20, volume_db=0,
    )
    p = new_project()
    mix, out_sr = AudioRenderer(sr).render(full, [ev], p.lane_states)
    assert out_sr == sr
    assert np.max(np.abs(mix)) > 0


def test_renderer_preview_hit():
    y, sr = _click()
    ev = DrumEvent(type='Kick', start=0.0, end=0.2, duration=0.2, punch=0.8)
    mix, _ = AudioRenderer(sr).render_single_hit(ev, y, new_project().lane_states)
    assert mix.shape[1] == 2
    assert np.max(np.abs(mix)) > 0


def test_project_save_load_roundtrip(tmp_path):
    p = new_project()
    p.source_path = 'test.wav'
    p.bpm = 128
    p.snap_enabled = True
    p.grid_fraction = 0.125
    e = DrumEvent(type='Snare', start=1.0, end=1.1, duration=0.1, fade_out_ms=15, source_offset_ms=5)
    p.events = [e]
    path = tmp_path / 'test.ndp'
    save_project(p, str(path))
    loaded = load_project(str(path))
    assert loaded.bpm == 128
    assert loaded.snap_enabled is True
    assert len(loaded.events) == 1
    assert loaded.events[0].fade_out_ms == 15
    assert loaded.events[0].source_offset_ms == 5


def test_paste_events_command():
    p = new_project()
    src = DrumEvent(type='Kick', start=0.5, end=0.58, duration=0.08)
    cb = [copy.deepcopy(src)]
    PasteEventsCommand(p, cb, 2.0, 'Kick', lambda: None).execute()
    assert len(p.events) == 1
    assert p.events[0].start == 2.0
