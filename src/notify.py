"""微信通知 (复用 ilinkai bot,跟 douyin-to-wechat 同一套)。"""
import base64
import json
import os
import secrets
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

ILINK_BASE = "https://ilinkai.weixin.qq.com"
BOT_TOKEN = os.getenv("ILINK_BOT_TOKEN", "")
BOT_ACCOUNT = os.getenv("ILINK_BOT_ACCOUNT", "")
USER_ID = os.getenv("ILINK_USER_ID", "")


def _headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BOT_TOKEN}",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": base64.b64encode(secrets.token_bytes(4)).decode(),
    }


def send_text(text: str, to_user: str = None) -> dict:
    if not BOT_TOKEN or not BOT_ACCOUNT:
        raise RuntimeError("缺少 ILINK_BOT_TOKEN / ILINK_BOT_ACCOUNT")
    to_user = to_user or USER_ID
    if not to_user:
        raise RuntimeError("缺少 ILINK_USER_ID")
    body = {
        "msg": {
            "from_user_id": BOT_ACCOUNT,
            "to_user_id": to_user,
            "client_id": secrets.token_hex(16),
            "message_type": 2,
            "message_state": 2,
            "context_token": "",
            "item_list": [{"type": 1, "text_item": {"text": text}}],
        }
    }
    r = requests.post(f"{ILINK_BASE}/ilink/bot/sendmessage",
                      headers=_headers(),
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      timeout=15)
    try:
        return r.json()
    except Exception:
        return {"http": r.status_code, "text": r.text[:200]}


def notify_3_pending(moments: list, deadline_min: int = 60) -> dict:
    """3 条朋友圈候选发到微信审核。"""
    parts = ["📱 今日朋友圈 3 条候选 (已渲图)\n"]
    for m in moments:
        parts.append(f"━━ {m['type'].upper()} (ID: {m['id'][:8]}) ━━")
        parts.append(m["text"])
        parts.append("")  # 空行
    parts.append("━━━━━━━━━━")
    parts.append(f"⏰ 各时段 {deadline_min} 分钟前不回,自动发")
    parts.append("发布时段: 10:00 / 14:00 / 20:00\n")
    parts.append("回复格式:")
    parts.append('  发 <ID>           立刻发')
    parts.append('  改 <ID> <意见>    Claude 重写')
    parts.append('  删 <ID>           取消这条')
    parts.append('  全发              3 条都批准')
    parts.append('  全删              3 条都取消')
    return send_text("\n".join(parts))


def notify_published(moment_id: str, type_: str, slot: str, text: str, ok: bool, err: str = "") -> dict:
    if ok:
        head = f"✅ 朋友圈已发 ({slot} / {type_})"
    else:
        head = f"❌ 朋友圈发布失败 ({slot} / {type_})"
    body = f"{head}\nID: {moment_id[:8]}\n{text[:80]}"
    if err:
        body += f"\nerr: {err[:200]}"
    return send_text(body)
