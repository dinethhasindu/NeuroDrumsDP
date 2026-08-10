from __future__ import annotations
import json
from pathlib import Path
from .models import ProjectState

def save_project(project: ProjectState, path: str):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(project.to_dict(), indent=2), encoding="utf-8")

def load_project(path: str) -> ProjectState:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ProjectState.from_dict(data)
