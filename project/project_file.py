"""
NeuroDrums AI - Project state saving and loading.
"""
from __future__ import annotations
import json
import os
from typing import Optional
from core.models import ProjectState, DrumEvent, LaneState, AudioInfo

def save_project(state: ProjectState, path: str) -> bool:
    """Save ProjectState to a JSON file."""
    try:
        data = {
            "version": state.version,
            "source_path": state.source_path,
            "drum_stem_path": state.drum_stem_path,
            "bpm": state.bpm,
            "time_signature_num": state.time_signature_num,
            "time_signature_den": state.time_signature_den,
            "zoom": state.zoom,
            "scroll_offset": state.scroll_offset,
            "events": [e.to_dict() for e in state.events],
            "lane_states": {
                k: {
                    "name": v.name,
                    "muted": v.muted,
                    "soloed": v.soloed,
                    "volume": v.volume,
                    "replacement_sample": v.replacement_sample,
                    "color": v.color
                } for k, v in state.lane_states.items()
            },
            "audio_info": None
        }

        if state.audio_info:
            data["audio_info"] = {
                "path": state.audio_info.path,
                "filename": state.audio_info.filename,
                "duration": state.audio_info.duration,
                "sample_rate": state.audio_info.sample_rate,
                "channels": state.audio_info.channels,
                "bit_depth": state.audio_info.bit_depth,
                "format": state.audio_info.format
            }

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save project: {e}")
        return False

def load_project(path: str) -> Optional[ProjectState]:
    """Load ProjectState from a JSON file."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)

        state = ProjectState(
            version=data.get("version", "1.0"),
            source_path=data.get("source_path", ""),
            drum_stem_path=data.get("drum_stem_path", ""),
            bpm=data.get("bpm", 120.0),
            time_signature_num=data.get("time_signature_num", 4),
            time_signature_den=data.get("time_signature_den", 4),
            zoom=data.get("zoom", 1.0),
            scroll_offset=data.get("scroll_offset", 0.0),
        )

        state.events = [DrumEvent.from_dict(e) for e in data.get("events", [])]

        state.lane_states = {}
        for k, v in data.get("lane_states", {}).items():
            state.lane_states[k] = LaneState(
                name=v.get("name", k),
                muted=v.get("muted", False),
                soloed=v.get("soloed", False),
                volume=v.get("volume", 1.0),
                replacement_sample=v.get("replacement_sample"),
                color=v.get("color", "#888888")
            )

        ai_data = data.get("audio_info")
        if ai_data:
            state.audio_info = AudioInfo(
                path=ai_data.get("path", ""),
                filename=ai_data.get("filename", ""),
                duration=ai_data.get("duration", 0.0),
                sample_rate=ai_data.get("sample_rate", 44100),
                channels=ai_data.get("channels", 1),
                bit_depth=ai_data.get("bit_depth", 16),
                format=ai_data.get("format", "WAV")
            )

        return state
    except Exception as e:
        print(f"Failed to load project: {e}")
        return None
