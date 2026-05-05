"""收集今日做过的事/发过的内容,作为 Claude 生成朋友圈的素材。

数据源:
1. 云端 douyin-to-wechat 的 queue.json (今日生成的公众号草稿)
2. 本地 zsxq-publisher 的 posts/ (今日发的星球文)
3. industry-knowledge-base 02-结构化总结/ (咨询案例摘要)
4. 各 GitHub 项目近 24h commit (今天做了啥)
"""
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))


def _today_iso():
    return datetime.now(CST).strftime("%Y-%m-%d")


def fetch_today_wechat_drafts() -> list:
    """SSH 云端拉今日生成的公众号草稿 (含标题 + 卡片摘要)。"""
    today = _today_iso()
    cmd = ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
           "root@121.36.105.43",
           f"python3 -c \"import json; d=json.load(open('/root/douyin-to-wechat/queue.json')); "
           f"items=[i for i in d if i.get('added_at','').startswith('{today}') or "
           f"(i.get('notified_at') or '').startswith('{today}') or "
           f"(i.get('published_at') or '').startswith('{today}')]; "
           f"print(json.dumps([{{'id':i['id'],'title':i.get('title'),'status':i['status']}} for i in items], ensure_ascii=False))\""]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout.strip()) if r.stdout.strip() else []
    except Exception as e:
        return [{"err": str(e)[:100]}]


def fetch_today_zsxq_posts(limit: int = 5) -> list:
    """读本地 zsxq-publisher posts/ 最近的归档。"""
    posts_dir = Path.home() / "zsxq-publisher" / "posts"
    if not posts_dir.exists():
        return []
    files = sorted(posts_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            text = d.get("text", "")
            # 只取标题行 + 前 200 字
            first_line = text.split("\n")[0][:50]
            out.append({"topic_id": d.get("topic_id"), "title": first_line, "excerpt": text[:300]})
        except Exception:
            continue
    return out


def fetch_consulting_summary() -> str:
    """读最新的咨询要点摘要 (industry-knowledge-base/02-结构化总结/)。"""
    kb = Path.home() / "industry-knowledge-base" / "02-结构化总结"
    if not kb.exists():
        # 兜底:从 /tmp/ikb 读 (之前 clone 过)
        kb = Path("/tmp/ikb/02-结构化总结")
    if not kb.exists():
        return ""
    md_files = sorted(kb.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not md_files:
        return ""
    # 取最新那份的前 2000 字
    return md_files[0].read_text(encoding="utf-8")[:2000]


def fetch_recent_git_activity(hours: int = 24) -> list:
    """各 ~/xxx 项目近 N 小时的 commit 摘要。"""
    results = []
    home = Path.home()
    for repo in home.iterdir():
        git_dir = repo / ".git"
        if not git_dir.exists() or not repo.is_dir():
            continue
        try:
            r = subprocess.run(
                ["git", "-C", str(repo), "log", f"--since={hours} hours ago",
                 "--pretty=format:%s", "--no-merges"],
                capture_output=True, text=True, timeout=10
            )
            commits = [l for l in r.stdout.splitlines() if l.strip()]
            if commits:
                results.append({"repo": repo.name, "commits": commits[:5]})
        except Exception:
            continue
    return results


def collect_all() -> dict:
    """一站式拉取所有数据源,返回打包好的字典 (供 Claude 生成时引用)。"""
    return {
        "today": _today_iso(),
        "wechat_drafts_today": fetch_today_wechat_drafts(),
        "zsxq_recent": fetch_today_zsxq_posts(5),
        "consulting_summary": fetch_consulting_summary(),
        "git_activity_24h": fetch_recent_git_activity(24),
    }


if __name__ == "__main__":
    import json as _j
    data = collect_all()
    print(_j.dumps(data, ensure_ascii=False, indent=2))
