from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL_DIR = PROJECT_ROOT / "jsonl"
IMAGE_ROOT = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
HOST = "0.0.0.0"
PORT = 8000
