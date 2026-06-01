"""Image serving with ETag caching and Range request support."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from backend.utils.datasets import normalize_image_rel


def serve_image(handler, rel_path: str, image_root: Path) -> None:
    """Serve an image file with ETag caching and Range request support.

    Args:
        handler: The BaseHTTPRequestHandler instance.
        rel_path: Relative path of the image under image_root.
        image_root: Root directory for images.
    """
    rel_path = normalize_image_rel(rel_path)
    full = (image_root / Path(rel_path)).resolve()
    if not str(full).startswith(str(image_root.resolve())):
        handler._send_json({"error": "access denied"}, 403)
        return
    if not full.is_file():
        handler._send_json({"error": "image not found"}, 404)
        return

    mime, _ = mimetypes.guess_type(str(full))
    if not mime:
        mime = "application/octet-stream"

    stat = full.stat()
    size = stat.st_size
    mtime = stat.st_mtime
    etag = hashlib.md5(f"{rel_path}-{mtime}-{size}".encode()).hexdigest()

    # Check If-None-Match for caching
    if_none = handler.headers.get("If-None-Match", "")
    if if_none.strip('"') == etag:
        handler.send_response(304)
        handler.send_header("ETag", f'"{etag}"')
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        return

    # Handle Range requests for large files
    range_header = handler.headers.get("Range")
    if range_header and range_header.startswith("bytes="):
        try:
            range_spec = range_header[6:]
            start_str, end_str = range_spec.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else size - 1
            end = min(end, size - 1)
            length = end - start + 1

            handler.send_response(206)
            handler.send_header("Content-Type", mime)
            handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            handler.send_header("Content-Length", str(length))
            handler.send_header("ETag", f'"{etag}"')
            handler.send_header("Cache-Control", "public, max-age=86400")
            handler.send_header("Access-Control-Allow-Origin", "*")
            handler.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, ETag")
            handler.end_headers()

            with open(full, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    send_len = min(len(chunk), remaining)
                    handler.wfile.write(chunk[:send_len])
                    remaining -= send_len
            return
        except (ValueError, IndexError):
            pass  # Fall through to full response

    # Full response
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(size))
    handler.send_header("ETag", f'"{etag}"')
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Expose-Headers", "Content-Length, ETag, Accept-Ranges")
    handler.end_headers()

    with open(full, "rb") as f:
        shutil.copyfileobj(f, handler.wfile, 65536)
