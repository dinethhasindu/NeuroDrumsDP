APP_NAME = 'NeuroDrums AI'
APP_VERSION = '1.1.0'
APP_SUBTITLE = 'AI Drum Stem Replacer'

LANE_NAMES = ['Kick', 'Snare', 'Closed Hat', 'Open Hat', 'Clap', 'Roll', 'Snare Roll', 'FX']
LANE_COLORS = {
    'Kick': '#ff4d6d', 'Snare': '#a855f7', 'Closed Hat': '#3b82f6', 'Open Hat': '#fbbf24',
    'Clap': '#fb923c', 'Roll': '#22c55e', 'Snare Roll': '#ec4899', 'FX': '#22d3ee'
}
LANE_SAMPLE_DIRS = {n: f"samples/{n.lower().replace(' ', '_')}" for n in LANE_NAMES}
LANE_HEIGHT = 82
LANE_HEADER_WIDTH = 190
RULER_HEIGHT = 34
MIN_ZOOM = 70.0
MAX_ZOOM = 900.0
DEFAULT_ZOOM = 120.0
DEFAULT_SR = 44100
HOP_LENGTH = 256
N_FFT = 2048
SENSITIVITY_PRESETS = {
    'low': {'delta': 0.32, 'wait': 7},
    'medium': {'delta': 0.20, 'wait': 3},
    'high': {'delta': 0.10, 'wait': 1},
}
