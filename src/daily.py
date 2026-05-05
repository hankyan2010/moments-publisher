"""主流程入口。

generate    早 8:00: 拉数据 → Claude 生 3 条 → 渲图 → 入库 → 通知微信
publish-slot <morning|noon|evening>  10/14/20 三个时段: 取该 slot 那条 → 发
                                      用户没回 = 自动发 (status=pending 等价 approved)
list-today  看今日 3 条状态
"""
import argparse
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_sources import collect_all
from generate import generate_3
from render_image import render
from store import init, add, get, update, list_by_date, get_today_slot, today_str, now_iso
from notify import notify_3_pending, notify_published
from publish import publish as publish_fn

SLOT_MAP = {"morning": "cognitive", "noon": "case", "evening": "persona"}


def cmd_generate():
    init()
    today = today_str()
    # 检查今日是否已生成 (避免重复)
    existing = list_by_date(today)
    if existing:
        print(f"[generate] 今日 {today} 已生成 {len(existing)} 条,跳过")
        return {"ok": True, "skipped": "already_generated", "count": len(existing)}

    print(f"[generate] 收集数据源...")
    data = collect_all()
    print(f"[generate] 调 Claude 生 3 条...")
    result = generate_3(data)
    moments = result.get("moments", [])
    backend = result.get("_backend", "")

    if len(moments) != 3:
        return {"ok": False, "error": f"Claude 生成数量异常: {len(moments)}"}

    type_to_slot = {v: k for k, v in SLOT_MAP.items()}
    saved = []
    for m in moments:
        type_ = m.get("type", "cognitive")
        slot = type_to_slot.get(type_, "morning")
        text = m.get("text", "").strip()
        if not text:
            continue
        # 视觉 prompt (Claude 输出的画面描述)
        image_prompt = m.get("image_prompt") or m.get("image_subject", "")
        # 即梦 t2i 生图
        try:
            img_path = render(type_, image_prompt)
        except Exception as e:
            print(f"  ⚠ 生图失败 ({type_}): {e}")
            img_path = ""
        mid = add(today, slot, type_, text, str(img_path) if img_path else "",
                  source_brief=image_prompt, claude_backend=backend)
        saved.append({"id": mid, "type": type_, "slot": slot, "text": text, "image": str(img_path)})
        print(f"  ✓ {mid[:8]} {type_} -> {img_path}")

    # 通知微信
    try:
        n = notify_3_pending(saved, deadline_min=60)
        print(f"[generate] notify: {n}")
    except Exception as e:
        print(f"[generate] notify err: {e}")
        n = {"err": str(e)}

    return {"ok": True, "action": "generate", "saved": saved, "notify": n}


def cmd_publish_slot(slot: str):
    init()
    item = get_today_slot(slot)
    if not item:
        print(f"[publish-slot] 今日 {slot} 没有候选")
        return {"ok": True, "skipped": "no_item", "slot": slot}
    if item.get("status") in ("published", "archived"):
        print(f"[publish-slot] {item['id'][:8]} 已 {item['status']}")
        return {"ok": True, "skipped": item["status"]}

    print(f"[publish-slot] 发: {item['id'][:8]} {item['type']} «{item['text'][:40]}»")
    try:
        r = publish_fn(item["text"], item.get("image_path"))
        ok = r.get("ok", False)
        if ok:
            update(item["id"], status="published", published_at=now_iso(),
                   published_proof=r.get("stdout", "")[:500])
        else:
            update(item["id"], status="failed", err=r.get("stderr", "")[:300])
        try:
            notify_published(item["id"], item["type"], slot, item["text"], ok,
                             err=r.get("stderr", "")[:200] if not ok else "")
        except Exception:
            pass
        return {"ok": ok, "result": r, "item_id": item["id"]}
    except Exception as e:
        traceback.print_exc()
        update(item["id"], status="failed", err=str(e)[:300])
        return {"ok": False, "error": str(e)}


def cmd_list_today():
    init()
    items = list_by_date(today_str())
    print(f"今日 {today_str()} 共 {len(items)} 条:")
    for i in items:
        print(f"  [{i['status']:10s}] {i['id'][:8]} | {i['slot']:8s} | {i['type']:10s} | {i['text'][:50]}")
    return items


def cmd_approve(item_id: str):
    """用户审核通过某条 (回『发 xxx』时调用)。"""
    init()
    item = get(item_id)
    if not item:
        return {"ok": False, "error": "id not found"}
    update(item["id"], status="approved")
    print(f"[approve] {item['id'][:8]} 已批准")
    return {"ok": True, "item": item}


def cmd_archive(item_id: str):
    init()
    item = get(item_id)
    if not item:
        return {"ok": False, "error": "id not found"}
    update(item["id"], status="archived")
    print(f"[archive] {item['id'][:8]} 已取消")
    return {"ok": True, "item": item}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate", help="早 8:00: 拉数据+生 3 条+通知微信")
    p_pub = sub.add_parser("publish-slot", help="发某时段那条")
    p_pub.add_argument("slot", choices=["morning", "noon", "evening"])
    sub.add_parser("list-today", help="看今日状态")
    p_app = sub.add_parser("approve", help="批准某条")
    p_app.add_argument("id")
    p_arc = sub.add_parser("archive", help="取消某条")
    p_arc.add_argument("id")
    args = p.parse_args()

    if args.cmd == "generate":
        out = cmd_generate()
    elif args.cmd == "publish-slot":
        out = cmd_publish_slot(args.slot)
    elif args.cmd == "list-today":
        out = cmd_list_today()
        return
    elif args.cmd == "approve":
        out = cmd_approve(args.id)
    elif args.cmd == "archive":
        out = cmd_archive(args.id)

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if out.get("ok") else 1)


if __name__ == "__main__":
    main()
