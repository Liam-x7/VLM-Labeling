"""Utilities for building record summaries, details, and stats."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from backend.utils.datasets import (
    checkpoint_from_image,
    extract_text_value,
    flatten_text_content,
    normalize_image_rel,
    parse_annotation_text,
    shorten_text,
)


def extract_messages(rec: dict) -> dict:
    """Extract system/user/assistant content from a record's messages."""
    system_prompt = ""
    user_content = ""
    assistant_content = ""
    for msg in rec.get("messages", []):
        role = msg.get("role")
        if role == "system":
            system_prompt = msg.get("content", "")
        elif role == "user":
            user_content = msg.get("content", "")
        elif role == "assistant":
            assistant_content = msg.get("content", "")
    return {
        "system_prompt": system_prompt,
        "user_content": user_content,
        "assistant_content": assistant_content,
    }


def is_annotated(system_prompt: str, user_content: str, assistant_content: str) -> bool:
    """Check whether a record has been fully annotated."""
    return bool(
        system_prompt and system_prompt.strip()
        and user_content and flatten_text_content(user_content).strip()
        and assistant_content and flatten_text_content(assistant_content).strip()
    )


def record_summary(name: str, cp: str, index: int, rec: dict) -> dict:
    """Build a summary view of a record for list display."""
    imgs = rec.get("images", [])
    img_rel = normalize_image_rel(imgs[0]) if imgs else ""
    img_name = Path(img_rel).name if img_rel else f"record-{index}"

    msgs = extract_messages(rec)
    system_prompt = msgs["system_prompt"]
    user_content = flatten_text_content(msgs["user_content"])
    assistant_content = msgs["assistant_content"]

    verdict = "Unknown"
    preview = ""
    if assistant_content:
        text = flatten_text_content(assistant_content)
        preview = shorten_text(text, 120)
        parsed = parse_annotation_text(text)
        verdict = parsed.get("verdict", "Unknown")

    annotated = is_annotated(system_prompt, user_content, assistant_content)

    return {
        "index": index,
        "image_rel": img_rel,
        "image_name": img_name,
        "checkpoint": cp,
        "verdict": verdict,
        "preview": preview,
        "image_url": f"/api/images/{quote(img_rel, safe='/')}" if img_rel else "",
        "annotated": annotated,
    }


def record_detail(name: str, cp: str, index: int, rec: dict) -> dict:
    """Build a full detail view of a record."""
    summary = record_summary(name, cp, index, rec)

    msgs = extract_messages(rec)
    assistant_content = msgs["assistant_content"]

    variants = extract_text_value(assistant_content)
    parsed = [parse_annotation_text(v) for v in variants]

    return {
        **summary,
        "system_prompt": msgs["system_prompt"],
        "user_content": flatten_text_content(msgs["user_content"]),
        "assistant_content": assistant_content,
        "assistant_variants": variants,
        "assistant_parsed": parsed,
    }


def compute_stats(records: list[dict]) -> dict:
    """Compute annotation statistics from a list of records."""
    cps: dict[str, dict] = {}

    for rec in records:
        imgs = rec.get("images", [])
        cp = checkpoint_from_image(imgs[0]) if imgs else "unassigned"
        if cp not in cps:
            cps[cp] = {"total": 0, "annotated": 0}
        cps[cp]["total"] += 1

        msgs = extract_messages(rec)
        if is_annotated(msgs["system_prompt"], flatten_text_content(msgs["user_content"]), msgs["assistant_content"]):
            cps[cp]["annotated"] += 1

    total = sum(v["total"] for v in cps.values())
    annotated = sum(v["annotated"] for v in cps.values())

    def _natural_sort_key(s: str):
        import re
        parts = re.findall(r"(\d+|\D+)", s.lower())
        return [int(p) if p.isdigit() else p for p in parts]

    return {
        "checkpoints": [
            {"name": cp, **stats}
            for cp, stats in sorted(cps.items(), key=lambda x: _natural_sort_key(x[0]))
        ],
        "total": total,
        "annotated": annotated,
        "unannotated": total - annotated,
    }
