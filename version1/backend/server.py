"""HTTP server with route handling for the label system."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote

from backend.config import JSONL_DIR, IMAGE_ROOT, FRONTEND_DIR, HOST, PORT
from backend.datastore import DataStore, _natural_sort_key
from backend.db import (
    init_db,
    register_user,
    login_user,
    logout_user,
    verify_token,
    list_pending_users,
    list_all_users,
    approve_user,
    reject_user,
    delete_user,
    get_user_by_username,
    change_password,
)
from backend.image_server import serve_image
from backend.record_utils import record_summary, record_detail, compute_stats


store = DataStore()


def create_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    init_db()
    handler = _make_handler(store)
    server = ThreadingHTTPServer((host, port), handler)
    return server


def _make_handler(data_store: DataStore):
    PUBLIC_PATHS = {
        "/api/health", "/", "/api/auth/login", "/api/auth/register",
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send_json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, data: bytes, filename: str, content_type: str = "application/octet-stream"):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def _serve_frontend_file(self, filename: str):
            file_path = FRONTEND_DIR / filename
            if not file_path.is_file():
                self._send_json({"error": "not found"}, 404)
                return
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            try:
                data = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self._send_json({"error": "internal error"}, 500)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}

        def _parse_path(self) -> str:
            return unquote(self.path.split("?")[0])

        def _get_token(self) -> str | None:
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                return auth[7:].strip()
            return None

        def _require_auth(self) -> dict | None:
            token = self._get_token()
            if not token:
                self._send_json({"error": "未登录"}, 401)
                return None
            user = verify_token(token)
            if not user:
                self._send_json({"error": "登录已过期，请重新登录"}, 401)
                return None
            return user

        def _require_admin(self) -> dict | None:
            user = self._require_auth()
            if user is None:
                return None
            if user["role"] != "admin":
                self._send_json({"error": "需要管理员权限"}, 403)
                return None
            return user

        # ---- GET ----
        def do_GET(self):
            path = self._parse_path()

            if path == "/api/health":
                self._send_json({"status": "ok"})
                return

            if path == "/":
                self._serve_frontend_file("index.html")
                return

            if path.startswith("/styles.css") or path.startswith("/app.js"):
                self._serve_frontend_file(path.lstrip("/"))
                return

            # Auth endpoints
            if path == "/api/auth/me":
                user = self._require_auth()
                if user is None:
                    return
                self._send_json({"username": user["username"], "role": user["role"]})
                return

            if path == "/api/auth/pending":
                user = self._require_admin()
                if user is None:
                    return
                self._send_json({"users": list_pending_users()})
                return

            if path == "/api/auth/users":
                user = self._require_admin()
                if user is None:
                    return
                self._send_json({"users": list_all_users()})
                return

            if path == "/api/admin/users":
                user = self._require_admin()
                if user is None:
                    return
                self._send_json({"users": list_all_users()})
                return

            # Image serving (no auth required — browser Image() doesn't send headers)
            if path.startswith("/api/images/"):
                serve_image(self, path[len("/api/images/"):], IMAGE_ROOT)
                return

            # Authenticated endpoints
            user = self._require_auth()
            if user is None:
                return

            if path == "/api/datasets":
                self._send_json({"datasets": data_store.discover()})
                return

            m = re.match(r"^/api/datasets/([^/]+)/checkpoints$", path)
            if m:
                cps = data_store.get_checkpoints(m.group(1))
                self._send_json({"checkpoints": cps})
                return

            m = re.match(r"^/api/datasets/([^/]+)/stats$", path)
            if m:
                records = data_store.get_all_records(m.group(1))
                self._send_json(compute_stats(records))
                return

            m = re.match(r"^/api/datasets/([^/]+)/records/(.+)$", path)
            if m:
                name, cp = m.group(1), unquote(m.group(2))
                records = data_store.get_records(name, cp)
                items = []
                for rec in records:
                    idx = rec.pop("_index")
                    items.append(record_summary(name, cp, idx, rec))
                self._send_json({"records": items})
                return

            m = re.match(r"^/api/records/([^/]+)/([^/]+)/(\d+)$", path)
            if m:
                name, cp, index = m.group(1), unquote(m.group(2)), int(m.group(3))
                rec = data_store.get_record(name, cp, index)
                if rec is None:
                    self._send_json({"error": "record not found"}, 404)
                    return
                self._send_json({"record": record_detail(name, cp, index, rec)})
                return

            m = re.match(r"^/api/datasets/([^/]+)/export$", path)
            if m:
                data = data_store.export_jsonl(m.group(1))
                if data is None:
                    self._send_json({"error": "dataset not found"}, 404)
                    return
                self._send_file(data, m.group(1), "application/x-jsonlines")
                return

            self._send_json({"error": "not found"}, 404)

        # ---- PUT ----
        def do_PUT(self):
            path = self._parse_path()

            if path == "/api/auth/password":
                user = self._require_auth()
                if user is None:
                    return
                body = self._read_body()
                result = change_password(user["username"], body.get("old_password", ""), body.get("new_password", ""))
                self._send_json(result, 200 if result["ok"] else 400)
                return

            user = self._require_auth()
            if user is None:
                return

            m = re.match(r"^/api/records/([^/]+)/([^/]+)/(\d+)$", path)
            if m:
                name, cp, index = m.group(1), unquote(m.group(2)), int(m.group(3))
                rec = data_store.save_record(name, cp, index, self._read_body())
                if rec is None:
                    self._send_json({"error": "record not found"}, 404)
                    return
                self._send_json({"record": record_detail(name, cp, index, rec)})
                return

            m = re.match(r"^/api/datasets/([^/]+)/records/([^/]+)/prompts$", path)
            if m:
                name, cp = m.group(1), unquote(m.group(2))
                count = data_store.batch_replace_prompts(name, cp, self._read_body())
                self._send_json({"replaced": count})
                return

            self._send_json({"error": "not found"}, 404)

        # ---- POST ----
        def do_POST(self):
            path = self._parse_path()

            # Public auth endpoints
            if path == "/api/auth/login":
                body = self._read_body()
                result = login_user(body.get("username", ""), body.get("password", ""))
                self._send_json(result, 200 if result["ok"] else 401)
                return

            if path == "/api/auth/register":
                body = self._read_body()
                result = register_user(body.get("username", ""), body.get("password", ""))
                self._send_json(result, 201 if result["ok"] else 400)
                return

            if path == "/api/auth/logout":
                token = self._get_token()
                if token:
                    logout_user(token)
                self._send_json({"ok": True})
                return

            # Admin management endpoints
            if path == "/api/auth/approve":
                user = self._require_admin()
                if user is None:
                    return
                result = approve_user(self._read_body().get("user_id"))
                self._send_json(result, 200 if result["ok"] else 400)
                return

            if path == "/api/auth/reject":
                user = self._require_admin()
                if user is None:
                    return
                result = reject_user(self._read_body().get("user_id"))
                self._send_json(result, 200 if result["ok"] else 400)
                return

            if path == "/api/auth/delete-user":
                user = self._require_admin()
                if user is None:
                    return
                result = delete_user(self._read_body().get("user_id"))
                self._send_json(result, 200 if result["ok"] else 400)
                return

            # RESTful admin routes (used by frontend)
            m_approve = re.match(r"^/api/admin/users/([^/]+)/approve$", path)
            if m_approve:
                self._admin_user_action(m_approve.group(1), approve_user)
                return

            m_reject = re.match(r"^/api/admin/users/([^/]+)/reject$", path)
            if m_reject:
                self._admin_user_action(m_reject.group(1), reject_user)
                return

            m_revoke = re.match(r"^/api/admin/users/([^/]+)/revoke$", path)
            if m_revoke:
                self._admin_user_action(m_revoke.group(1), delete_user)
                return

            # Change password
            if path == "/api/auth/change-password":
                user = self._require_auth()
                if user is None:
                    return
                body = self._read_body()
                result = change_password(user["username"], body.get("old_password", ""), body.get("new_password", ""))
                self._send_json(result, 200 if result["ok"] else 400)
                return

            # Authenticated endpoints
            user = self._require_auth()
            if user is None:
                return

            if path == "/api/datasets/upload":
                self._handle_upload()
                return

            m = re.match(r"^/api/datasets/([^/]+)/scan$", path)
            if m:
                self._send_json(data_store.scan_images(m.group(1)))
                return

            self._send_json({"error": "not found"}, 404)

        def _admin_user_action(self, username: str, action_fn):
            """Common handler for admin user actions (approve/reject/revoke)."""
            user = self._require_admin()
            if user is None:
                return
            target = get_user_by_username(unquote(username))
            if target is None:
                self._send_json({"error": "用户不存在"}, 404)
                return
            result = action_fn(target["id"])
            self._send_json(result, 200 if result["ok"] else 400)

        # ---- CORS ----
        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

        def _handle_upload(self):
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self._send_json({"error": "no file"}, 400)
                return

            body = self.rfile.read(length)

            if "multipart/form-data" in content_type:
                boundary = content_type.split("boundary=")[-1]
                if not boundary:
                    self._send_json({"error": "invalid upload"}, 400)
                    return
                filename = self._extract_filename(body, boundary.encode())
                if not filename:
                    self._send_json({"error": "no filename"}, 400)
                    return
                file_data = self._extract_file_body(body, boundary.encode())
            else:
                filename = self.headers.get("X-Filename", "")
                if not filename:
                    self._send_json({"error": "X-Filename header required"}, 400)
                    return
                file_data = body

            if not filename.endswith(".jsonl"):
                self._send_json({"error": "file must be .jsonl"}, 400)
                return

            filename = re.sub(r"[^a-zA-Z0-9_\-\.\u4e00-\u9fff]", "_", filename)
            dest = JSONL_DIR / filename

            if dest.exists():
                self._send_json({"error": f"file {filename} already exists"}, 409)
                return

            try:
                for line in file_data.decode("utf-8-sig").splitlines():
                    if line.strip():
                        json.loads(line)
            except Exception as e:
                self._send_json({"error": f"invalid JSONL: {e}"}, 400)
                return

            dest.write_bytes(file_data)
            self._send_json({"name": filename, "message": f"uploaded {filename}"}, 201)

        def _extract_filename(self, body: bytes, boundary: bytes) -> str:
            text = body.decode("utf-8", errors="replace")
            m = re.search(r'filename="([^"]+)"', text)
            return m.group(1) if m else ""

        def _extract_file_body(self, body: bytes, boundary: bytes) -> bytes:
            parts = body.split(b"--" + boundary)
            for part in parts:
                if b"\r\n\r\n" in part:
                    header, _, data = part.partition(b"\r\n\r\n")
                    return data.rstrip(b"\r\n").rstrip(b"--")
            return b""

    return Handler
