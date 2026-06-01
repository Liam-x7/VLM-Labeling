"""Thread-safe in-memory cache of JSONL datasets."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from backend.config import JSONL_DIR, IMAGE_ROOT
from backend.utils.datasets import checkpoint_from_image, normalize_image_rel

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _natural_sort_key(s: str):
    """Split string into text and number parts for natural sorting."""
    parts = re.findall(r"(\d+|\D+)", s.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def _build_placeholder_record(image_rel: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
        ],
        "images": [f"data/{image_rel}"],
    }


class DataStore:
    """Thread-safe in-memory cache of JSONL datasets."""

    def __init__(self):
        self.lock = threading.RLock()
        self._datasets: dict[str, list[dict]] = {}

    def _jsonl_path(self, name: str) -> Path:
        return JSONL_DIR / name

    def discover(self) -> list[dict]:
        with self.lock:
            self._scan_all()
            result = []
            for name, records in sorted(self._datasets.items()):
                cps: dict[str, int] = {}
                for rec in records:
                    imgs = rec.get("images", [])
                    cp = checkpoint_from_image(imgs[0]) if imgs else "unassigned"
                    cps[cp] = cps.get(cp, 0) + 1
                result.append({
                    "name": name,
                    "total": len(records),
                    "checkpoints": sorted(cps.items(), key=lambda x: _natural_sort_key(x[0])),
                })
            return result

    def _scan_all(self) -> None:
        if not JSONL_DIR.exists():
            return
        existing = {f.name for f in JSONL_DIR.glob("*.jsonl")}
        for name in existing:
            if name not in self._datasets:
                self._load_file(name)

    def _load_file(self, name: str) -> None:
        path = self._jsonl_path(name)
        records = []
        try:
            with path.open("r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            return
        if records:
            self._datasets[name] = records

    def get_checkpoints(self, name: str) -> list[dict]:
        with self.lock:
            self._scan_all()
            records = self._datasets.get(name, [])
            cps: dict[str, int] = {}
            for rec in records:
                imgs = rec.get("images", [])
                cp = checkpoint_from_image(imgs[0]) if imgs else "unassigned"
                cps[cp] = cps.get(cp, 0) + 1
            return [
                {"name": cp, "count": cnt}
                for cp, cnt in sorted(cps.items(), key=lambda x: _natural_sort_key(x[0]))
            ]

    def get_records(self, name: str, cp: str) -> list[dict]:
        with self.lock:
            self._scan_all()
            records = self._datasets.get(name, [])
            result = []
            for i, rec in enumerate(records):
                imgs = rec.get("images", [])
                rec_cp = checkpoint_from_image(imgs[0]) if imgs else "unassigned"
                if rec_cp == cp:
                    result.append({**rec, "_index": i})
            return result

    def get_record(self, name: str, cp: str, index: int) -> dict | None:
        with self.lock:
            self._scan_all()
            records = self._datasets.get(name, [])
            if index < 0 or index >= len(records):
                return None
            rec = records[index]
            imgs = rec.get("images", [])
            rec_cp = checkpoint_from_image(imgs[0]) if imgs else "unassigned"
            if rec_cp != cp:
                return None
            return rec

    def save_record(self, name: str, cp: str, index: int, payload: dict) -> dict | None:
        with self.lock:
            self._scan_all()
            records = self._datasets.get(name)
            if records is None or index < 0 or index >= len(records):
                return None
            rec = records[index]
            imgs = rec.get("images", [])
            rec_cp = checkpoint_from_image(imgs[0]) if imgs else "unassigned"
            if rec_cp != cp:
                return None

            system_prompt = payload.get("system_prompt")
            user_content = payload.get("user_content")
            assistant_content = payload.get("assistant_content")

            if system_prompt is not None:
                for msg in rec.get("messages", []):
                    if msg.get("role") == "system":
                        msg["content"] = system_prompt
                        break

            if user_content is not None:
                for msg in rec.get("messages", []):
                    if msg.get("role") == "user":
                        msg["content"] = user_content
                        break

            if assistant_content is not None:
                for msg in rec.get("messages", []):
                    if msg.get("role") == "assistant":
                        msg["content"] = assistant_content
                        break

            path = self._jsonl_path(name)
            with path.open("w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

            return rec

    def scan_images(self, name: str) -> dict:
        with self.lock:
            self._scan_all()
            records = self._datasets.get(name, [])

            existing_images = set()
            for rec in records:
                for img in rec.get("images", []):
                    existing_images.add(normalize_image_rel(img))

            new_images: list[str] = []
            if IMAGE_ROOT.exists():
                for cp_dir in sorted(IMAGE_ROOT.iterdir()):
                    if not cp_dir.is_dir() or cp_dir.name.startswith("."):
                        continue
                    for img_file in sorted(cp_dir.iterdir()):
                        if img_file.suffix.lower() in IMAGE_EXTENSIONS:
                            rel = f"{cp_dir.name}/{img_file.name}"
                            if rel not in existing_images:
                                new_images.append(rel)

            if not new_images:
                return {"new_count": 0, "message": "没有新图片"}

            path = self._jsonl_path(name)
            with path.open("a", encoding="utf-8") as f:
                for img_rel in new_images:
                    rec = _build_placeholder_record(img_rel)
                    records.append(rec)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

            new_cps: dict[str, int] = {}
            for img_rel in new_images:
                cp = checkpoint_from_image(img_rel)
                new_cps[cp] = new_cps.get(cp, 0) + 1

            return {
                "new_count": len(new_images),
                "checkpoints": sorted(new_cps.items(), key=lambda x: _natural_sort_key(x[0])),
                "message": f"新增 {len(new_images)} 条记录",
            }

    def batch_replace_prompts(self, name: str, cp: str, payload: dict) -> int:
        with self.lock:
            self._scan_all()
            records = self._datasets.get(name)
            if records is None:
                return 0

            system_prompt = payload.get("system_prompt")
            user_content = payload.get("user_content")

            count = 0
            for rec in records:
                imgs = rec.get("images", [])
                rec_cp = checkpoint_from_image(imgs[0]) if imgs else "unassigned"
                if rec_cp != cp:
                    continue

                if system_prompt is not None:
                    for msg in rec.get("messages", []):
                        if msg.get("role") == "system":
                            msg["content"] = system_prompt
                            break

                if user_content is not None:
                    for msg in rec.get("messages", []):
                        if msg.get("role") == "user":
                            msg["content"] = user_content
                            break

                count += 1

            path = self._jsonl_path(name)
            with path.open("w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

            return count

    def export_jsonl(self, name: str) -> bytes | None:
        """Export a dataset as JSONL bytes."""
        with self.lock:
            self._scan_all()
            records = self._datasets.get(name)
            if records is None:
                return None
            lines = [json.dumps(r, ensure_ascii=False) for r in records]
            return "\n".join(lines).encode("utf-8")

    def get_all_records(self, name: str) -> list[dict]:
        """Return all records for a dataset (for stats computation)."""
        with self.lock:
            self._scan_all()
            return list(self._datasets.get(name, []))
