"""SQLite database for user management with admin-approval registration."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from pathlib import Path

from backend.config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "label_system.db"

# 简单的 token 存储: token -> username
_tokens: dict[str, str] = {}
_tokens_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return hashed, salt


def init_db() -> None:
    """Initialize database and create default admin account if not exists."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # 创建默认 admin 账号
        cur = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        if cur.fetchone() is None:
            hashed, salt = _hash_password("admin")
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, status) VALUES (?, ?, ?, ?, ?)",
                ("admin", hashed, salt, "admin", "approved"),
            )
            conn.commit()
    finally:
        conn.close()


def register_user(username: str, password: str) -> dict:
    """Register a new user (status=pending, needs admin approval)."""
    if not username or not password:
        return {"ok": False, "error": "用户名和密码不能为空"}
    if len(username) < 2 or len(username) > 32:
        return {"ok": False, "error": "用户名长度需在2-32之间"}
    if len(password) < 4:
        return {"ok": False, "error": "密码长度至少4位"}

    hashed, salt = _hash_password(password)
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, status) VALUES (?, ?, ?, ?, ?)",
            (username, hashed, salt, "user", "pending"),
        )
        conn.commit()
        return {"ok": True, "message": "注册申请已提交，等待管理员审批"}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "用户名已存在"}
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict:
    """Authenticate user and return a token if approved."""
    if not username or not password:
        return {"ok": False, "error": "用户名和密码不能为空"}

    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT id, username, password_hash, salt, role, status FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "用户名或密码错误"}

        hashed, _ = _hash_password(password, row["salt"])
        if hashed != row["password_hash"]:
            return {"ok": False, "error": "用户名或密码错误"}

        if row["status"] != "approved":
            return {"ok": False, "error": "账号尚未通过管理员审批"}

        # 生成 token
        token = os.urandom(32).hex()
        with _tokens_lock:
            _tokens[token] = row["username"]

        return {
            "ok": True,
            "token": token,
            "username": row["username"],
            "role": row["role"],
        }
    finally:
        conn.close()


def logout_user(token: str) -> None:
    with _tokens_lock:
        _tokens.pop(token, None)


def verify_token(token: str) -> dict | None:
    """Verify token and return user info."""
    with _tokens_lock:
        username = _tokens.get(token)
    if username is None:
        return None

    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT username, role, status FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if row is None or row["status"] != "approved":
            return None
        return {"username": row["username"], "role": row["role"]}
    finally:
        conn.close()


def list_pending_users() -> list[dict]:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT id, username, created_at FROM users WHERE status = 'pending' ORDER BY created_at"
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_all_users() -> list[dict]:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT id, username, role, status, created_at FROM users ORDER BY created_at"
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def approve_user(user_id: int) -> dict:
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT username, status FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "用户不存在"}
        if row["status"] == "approved":
            return {"ok": False, "error": "用户已通过审批"}
        conn.execute("UPDATE users SET status = 'approved' WHERE id = ?", (user_id,))
        conn.commit()
        return {"ok": True, "message": f"已批准用户 {row['username']}"}
    finally:
        conn.close()


def reject_user(user_id: int) -> dict:
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT username, status FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "用户不存在"}
        if row["status"] == "approved":
            return {"ok": False, "error": "已通过审批的用户不能拒绝"}
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return {"ok": True, "message": f"已拒绝并删除用户 {row['username']}"}
    finally:
        conn.close()


def delete_user(user_id: int) -> dict:
    conn = _get_conn()
    try:
        cur = conn.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "用户不存在"}
        if row["role"] == "admin":
            return {"ok": False, "error": "不能删除管理员账号"}
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        # 清除该用户的 token
        with _tokens_lock:
            to_remove = [t for t, u in _tokens.items() if u == row["username"]]
            for t in to_remove:
                del _tokens[t]
        return {"ok": True, "message": f"已删除用户 {row['username']}"}
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    """Get user info by username. Returns dict with id, username, role, status or None."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT id, username, role, status FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def change_password(username: str, old_password: str, new_password: str) -> dict:
    if len(new_password) < 4:
        return {"ok": False, "error": "新密码长度至少4位"}

    conn = _get_conn()
    try:
        cur = conn.execute(
            "SELECT password_hash, salt FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if row is None:
            return {"ok": False, "error": "用户不存在"}

        hashed, _ = _hash_password(old_password, row["salt"])
        if hashed != row["password_hash"]:
            return {"ok": False, "error": "原密码错误"}

        new_hashed, new_salt = _hash_password(new_password)
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (new_hashed, new_salt, username),
        )
        conn.commit()
        return {"ok": True, "message": "密码修改成功"}
    finally:
        conn.close()
