from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ITEM_LINE_RE = re.compile(r"^\s*(\d+)[\.\、]\s*(.+?)\s*$")
VERDICT_RE = re.compile(r"(?:质检结论|结论|verdict)\s*[:：]\s*(pass|fail|unknown)", re.IGNORECASE)
REASON_RE = re.compile(r"(?:不合格原因|原因|reason)\s*[:：]\s*(.+)$", re.IGNORECASE)
STATUS_RE = re.compile(r"[\[(]?\s*(✓|✔|✗|×|x|X|pass|fail)\s*[\])]?\s*$", re.IGNORECASE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_image_rel(path: str) -> str:
    value = str(path or "").replace("\\", "/").strip()
    if value.startswith("data/"):
        value = value[5:]
    return value.lstrip("/")


def default_output_path_for_dataset(dataset_path: Path) -> Path:
    return dataset_path.with_suffix(".edited.jsonl")


def flatten_text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "text" in value:
            return flatten_text_content(value.get("text"))
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(flatten_text_content(item.get("text")))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "".join(parts)
    return "" if value is None else str(value)


def extract_text_value(content: Any) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return [text]
        if isinstance(text, list):
            return [str(item) for item in text]
    return [json.dumps(content, ensure_ascii=False, indent=2)]


def infer_assistant_mode(content: Any) -> str:
    if isinstance(content, dict):
        return "dict_text"
    return "string"


def build_assistant_content(mode: str, variants: list[str]) -> Any:
    clean_variants = [str(item).replace("\r\n", "\n") for item in variants]
    if mode == "dict_text" or len(clean_variants) > 1:
        return {"text": clean_variants}
    return clean_variants[0] if clean_variants else ""


def normalize_verdict(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered == "pass":
        return "Pass"
    if lowered == "fail":
        return "Fail"
    return "Unknown"


def parse_annotation_text(text: str) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    verdict = "Unknown"
    reason = ""

    for raw_line in str(text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        verdict_match = VERDICT_RE.search(line)
        if verdict_match:
            verdict = normalize_verdict(verdict_match.group(1))
            continue

        reason_match = REASON_RE.search(line)
        if reason_match:
            reason = reason_match.group(1).strip()
            continue

        item_match = ITEM_LINE_RE.match(line)
        if not item_match:
            continue

        index = int(item_match.group(1))
        body = item_match.group(2)
        name = body
        observation = ""
        status = "pass"

        for separator in ("：", ":"):
            if separator in body:
                name, observation = body.split(separator, 1)
                break

        status_match = STATUS_RE.search(observation or body)
        if status_match:
            marker = status_match.group(1).lower()
            status = "fail" if marker in {"✗", "×", "x", "fail"} else "pass"
            target = observation if observation else body
            cleaned = target[: status_match.start()].strip()
            if observation:
                observation = cleaned
            else:
                observation = cleaned.replace(name, "", 1).strip()

        observation = re.sub(r"^\[?观察\]?", "", observation).strip()
        items.append(
            {
                "index": index,
                "name": name.strip(),
                "observation": observation,
                "status": status,
            }
        )

    return {"items": items, "verdict": verdict, "reason": reason}


def checkpoint_from_image(image_rel: str) -> str:
    parts = Path(normalize_image_rel(image_rel)).parts
    return parts[0] if parts else ""


def safe_json_loads(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def resolve_path(workspace_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (workspace_root / path).resolve()


def ensure_jsonl_file(workspace_root: Path, value: str | Path) -> Path:
    path = resolve_path(workspace_root, value)
    if path.suffix.lower() != ".jsonl":
        raise ValueError("dataset file must be a .jsonl file")
    if not path.exists() or not path.is_file():
        raise ValueError(f"dataset file does not exist: {path}")
    return path


def ensure_directory(workspace_root: Path, value: str | Path) -> Path:
    path = resolve_path(workspace_root, value)
    if not path.exists() or not path.is_dir():
        raise ValueError(f"directory does not exist: {path}")
    return path


def count_jsonl_records(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def build_dataset_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    if not slug:
        slug = "dataset"
    return f"{slug}-{uuid4().hex[:8]}"


def shorten_text(value: str, limit: int = 120) -> str:
    compact = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        text = str(value or "")
        items = re.split(r"[,\n，]+", text)
    tags: list[str] = []
    seen: set[str] = set()
    for raw in items:
        tag = str(raw or "").strip()
        if not tag:
            continue
        lowered = tag.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        tags.append(tag)
    return tags
