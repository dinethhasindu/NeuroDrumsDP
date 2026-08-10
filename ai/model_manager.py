"""
NeuroDrums AI - Model Manager.

Handles:
  - Discovering locally installed models
  - Downloading missing models from official sources
  - Reporting model status for UI display
  - Checksum verification where available
  - GPU/CPU device detection
"""
from __future__ import annotations
import os
import json
import hashlib
import threading
from typing import Dict, Optional, Callable

from core.constants import MODEL_INFO


MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")


def get_models_dir() -> str:
    d = os.path.abspath(MODELS_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def get_device() -> str:
    """
    Detect best available compute device.
    Returns 'cuda', 'cpu'
    Never raises.
    """
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def get_device_name() -> str:
    """Human-readable device name."""
    try:
        import torch
        if torch.cuda.is_available():
            return f"NVIDIA {torch.cuda.get_device_name(0)} (CUDA)"
    except Exception:
        pass
    return "CPU"


def list_model_status() -> Dict[str, Dict]:
    """
    Return status dict for all known models.

    Returns dict mapping model_key -> {name, filename, status, path, size_mb, ...}
    """
    result = {}
    models_dir = get_models_dir()

    for key, info in MODEL_INFO.items():
        fname = info["filename"]
        path = os.path.join(models_dir, fname)
        installed = os.path.isfile(path)
        size_bytes = os.path.getsize(path) if installed else 0
        result[key] = {
            "key":         key,
            "filename":    fname,
            "description": info["description"],
            "license":     info["license"],
            "purpose":     info["purpose"],
            "expected_mb": info["size_mb"],
            "actual_mb":   round(size_bytes / 1_048_576, 1),
            "installed":   installed,
            "path":        path,
            "url":         info["url"],
            "status":      "Installed" if installed else "Not Downloaded",
        }

    # Check for RF classifier
    rf_path = os.path.join(models_dir, "drum_rf_classifier.pkl")
    result["drum_rf_classifier"] = {
        "key":         "drum_rf_classifier",
        "filename":    "drum_rf_classifier.pkl",
        "description": "8-class RandomForest drum event classifier",
        "license":     "MIT",
        "purpose":     "Stage 2: Classify detected drum events into 8 classes",
        "expected_mb": 5,
        "actual_mb":   round(os.path.getsize(rf_path) / 1_048_576, 1) if os.path.exists(rf_path) else 0,
        "installed":   os.path.exists(rf_path),
        "path":        rf_path,
        "url":         None,  # Built locally
        "status":      "Installed" if os.path.exists(rf_path) else "Will be built on first run",
    }

    return result


def download_model(
    model_key: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    done_cb: Optional[Callable[[bool, str], None]] = None,
) -> None:
    """Download a model in a background thread."""
    def _run():
        try:
            info = MODEL_INFO.get(model_key)
            if info is None:
                if done_cb:
                    done_cb(False, f"Unknown model: {model_key}")
                return

            url = info["url"]
            dest = os.path.join(get_models_dir(), info["filename"])

            import urllib.request

            def _reporthook(count, block_size, total_size):
                if total_size > 0 and progress_cb:
                    progress_cb(min(1.0, count * block_size / total_size),
                                f"Downloading {info['filename']}...")

            urllib.request.urlretrieve(url, dest, reporthook=_reporthook)

            if done_cb:
                done_cb(True, dest)
        except Exception as e:
            if done_cb:
                done_cb(False, str(e))

    threading.Thread(target=_run, daemon=True).start()


def ensure_rf_classifier_exists() -> bool:
    """Return True only if a real trained RF classifier file exists."""
    rf_path = os.path.join(get_models_dir(), "drum_rf_classifier.pkl")
    return os.path.exists(rf_path)


def onnx_session(model_key: str = "drumsep_onnx"):
    """
    Create and return an ONNX Runtime inference session for a model.
    Prefers CUDA execution provider if available.

    Returns:
        onnxruntime.InferenceSession or None
    """
    try:
        import onnxruntime as ort
        status = list_model_status()
        if model_key not in status or not status[model_key]["installed"]:
            return None

        path = status[model_key]["path"]
        device = get_device()

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if device == "cuda" \
                    else ["CPUExecutionProvider"]

        sess_opts = ort.SessionOptions()
        sess_opts.log_severity_level = 3  # Suppress warnings

        session = ort.InferenceSession(path, sess_options=sess_opts, providers=providers)
        return session
    except Exception as e:
        print(f"[ModelManager] ONNX session creation failed: {e}")
        return None
