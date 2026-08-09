"""
NeuroDrums AI - Core constants.
Central source of truth for lane names, colors, and global settings.
"""

# ── Drum lanes ──────────────────────────────────────────────────────────────
LANE_NAMES = ["Kick", "Snare", "Closed Hat", "Open Hat", "Clap", "Roll", "Snare Roll", "FX"]

LANE_COLORS = {
    "Kick":       "#ff4d6d",
    "Snare":      "#9d4edd",
    "Closed Hat": "#3a86ff",
    "Open Hat":   "#ffbe0b",
    "Clap":       "#fb5607",
    "Roll":       "#2dc653",
    "Snare Roll": "#f72585",
    "FX":         "#00b4d8",
}

LANE_COLORS_DIM = {
    k: v + "55" for k, v in LANE_COLORS.items()
}

LANE_SAMPLE_DIRS = {
    "Kick":       "samples/kick",
    "Snare":      "samples/snare",
    "Closed Hat": "samples/closed_hat",
    "Open Hat":   "samples/open_hat",
    "Clap":       "samples/clap",
    "Roll":       "samples/roll",
    "Snare Roll": "samples/snare_roll",
    "FX":         "samples/fx",
}

# ── Event types (canonical) ──────────────────────────────────────────────────
EVENT_TYPES = LANE_NAMES  # alias

# ── Sub-type mapping → primary lane ─────────────────────────────────────────
SUBTYPE_MAP = {
    "Ghost Snare":  "Snare",
    "Rim":          "Snare",
    "Rimshot":      "Snare",
    "Crash":        "FX",
    "Ride":         "FX",
    "Tom":          "FX",
    "808 Kick":     "Kick",
    "Layered Kick": "Kick",
    "Layered Snare":"Snare",
    "Percussion":   "FX",
    "Hi-Hat":       "Closed Hat",
    "Open Hi-Hat":  "Open Hat",
}

# ── Detection sensitivity presets ────────────────────────────────────────────
SENSITIVITY_PRESETS = {
    "low":    {"delta": 0.35, "pre_max": 12, "post_max": 12, "pre_avg": 20, "post_avg": 20, "wait": 6},
    "medium": {"delta": 0.20, "pre_max": 8,  "post_max": 8,  "pre_avg": 16, "post_avg": 16, "wait": 3},
    "high":   {"delta": 0.10, "pre_max": 4,  "post_max": 4,  "pre_avg": 8,  "post_avg": 8,  "wait": 1},
}

# ── UI layout ────────────────────────────────────────────────────────────────
LANE_HEIGHT = 90          # pixels per lane row
RULER_HEIGHT = 32         # pixels for timeline ruler
LANE_HEADER_WIDTH = 180   # pixels for lane label + controls on left
MIN_ZOOM = 1.0
MAX_ZOOM = 200.0

# ── Audio ────────────────────────────────────────────────────────────────────
DEFAULT_SR = 44100
HOP_LENGTH = 256
N_FFT = 2048

# ── Model info ───────────────────────────────────────────────────────────────
MODEL_INFO = {
    "drumsep_onnx": {
        "filename": "drumsep.onnx",
        "url": "https://huggingface.co/gridshiftstudio/drumsep-onnx/resolve/main/drumsep.onnx",
        "size_mb": 320,
        "license": "MIT",
        "description": "DrumSep 4-class drum source separator (kick/snare/cymbal/tom)",
        "purpose": "Stage 1b: Separate individual drum components for feature extraction",
    },
}

# ── Version ───────────────────────────────────────────────────────────────────
APP_VERSION = "1.0.0"
APP_NAME = "NeuroDrums AI"
APP_SUBTITLE = "AI Drum Stem Replacer"
