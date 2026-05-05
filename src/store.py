"""朋友圈状态库 (SQLite)。每条朋友圈 = 一个 moment 行。"""
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
DB = Path(__file__).parent.parent / "moments.db"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS moments (
      id TEXT PRIMARY KEY,
      date TEXT NOT NULL,                  -- 2026-05-05 北京时间
      slot TEXT NOT NULL,                  -- morning / noon / evening
      type TEXT NOT NULL,                  -- cognitive / case / persona
      text TEXT NOT NULL,
      image_path TEXT,
      status TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / published / failed / archived
      generated_at TEXT NOT NULL,
      notified_at TEXT,
      published_at TEXT,
      published_proof TEXT,                -- OCR 验证截图路径
      source_brief TEXT,
      claude_backend TEXT,
      err TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_moments_date ON moments(date);
    CREATE INDEX IF NOT EXISTS ix_moments_status ON moments(status);
    """)
    c.commit()
    c.close()


def now_iso():
    return datetime.now(CST).isoformat(timespec="seconds")


def today_str():
    return datetime.now(CST).strftime("%Y-%m-%d")


def add(date: str, slot: str, type_: str, text: str,
        image_path: str = "", source_brief: str = "", claude_backend: str = "") -> str:
    mid = uuid.uuid4().hex[:12]
    c = _conn()
    c.execute("""INSERT INTO moments (id, date, slot, type, text, image_path,
                                       status, generated_at, source_brief, claude_backend)
                  VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
              (mid, date, slot, type_, text, image_path, now_iso(), source_brief, claude_backend))
    c.commit()
    c.close()
    return mid


def get(mid: str) -> dict:
    c = _conn()
    r = c.execute("SELECT * FROM moments WHERE id=? OR id LIKE ?", (mid, mid + "%")).fetchone()
    c.close()
    return dict(r) if r else None


def update(mid: str, **fields):
    if not fields:
        return
    keys = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [mid]
    c = _conn()
    c.execute(f"UPDATE moments SET {keys} WHERE id=?", vals)
    c.commit()
    c.close()


def list_by_date(date: str) -> list:
    c = _conn()
    rows = c.execute("SELECT * FROM moments WHERE date=? ORDER BY slot", (date,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def list_by_status(status: str, limit: int = 50) -> list:
    c = _conn()
    rows = c.execute("SELECT * FROM moments WHERE status=? ORDER BY date DESC, slot LIMIT ?",
                     (status, limit)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_today_slot(slot: str) -> dict:
    """拿今天某 slot 的那条 (审核后才有 approved 状态,自动兜底也算 approved)。"""
    c = _conn()
    r = c.execute("""SELECT * FROM moments WHERE date=? AND slot=?
                     AND status IN ('approved', 'pending')
                     ORDER BY generated_at DESC LIMIT 1""",
                  (today_str(), slot)).fetchone()
    c.close()
    return dict(r) if r else None


if __name__ == "__main__":
    init()
    print(f"DB: {DB}")
