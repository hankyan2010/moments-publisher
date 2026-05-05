"""发布执行。

两种部署模式:
- LOCAL_MODE=1   本机就是 mac mini,直接调本地 post_image.py (推荐)
- LOCAL_MODE=0   远程模式: scp 图到 mac mini → ssh 跑 post_image.py
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

LOCAL_MODE = os.getenv("LOCAL_MODE", "0") == "1"
MAC_MINI_USER = os.getenv("MAC_MINI_USER", "guiguixiaxia")
MAC_MINI_HOST = os.getenv("MAC_MINI_HOST", "100.83.64.123")
MAC_MINI_REMOTE_TMP = os.getenv("MAC_MINI_REMOTE_TMP", "/tmp/moments-publisher")
POST_IMAGE_SCRIPT = os.getenv("POST_IMAGE_SCRIPT",
                              "/Users/guiguixiaxia/wechat-moments-sync/remote/post_image.py")


def _ssh(cmd: str, timeout: int = 30) -> tuple:
    full = ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
            f"{MAC_MINI_USER}@{MAC_MINI_HOST}", cmd]
    r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def _scp(local: str, remote: str, timeout: int = 180) -> tuple:
    """tailscale 偶尔慢,大图 (1-2MB) 给 3 分钟。"""
    cmd = ["scp", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes",
           "-C",  # 启用 ssh 压缩,加速 PNG 传输
           local, f"{MAC_MINI_USER}@{MAC_MINI_HOST}:{remote}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def _publish_local(text: str, image_path: str = None) -> dict:
    """本地模式:已经在 mac mini 上,直接调 post_image.py 不走 SSH。"""
    ts = int(time.time())
    work_dir = Path(MAC_MINI_REMOTE_TMP) / str(ts)
    work_dir.mkdir(parents=True, exist_ok=True)
    images = []
    if image_path:
        src = Path(image_path)
        if not src.exists():
            return {"ok": False, "stage": "image_check", "err": f"本地图不存在: {image_path}"}
        # 复制到 post_image 期望的临时目录 (与 wechat-moments-sync 兼容)
        dst = work_dir / src.name
        shutil.copy2(src, dst)
        images = [str(dst)]
    payload = json.dumps({"text": text, "images": images}, ensure_ascii=False)
    cmd = ["/usr/bin/env", "python3", POST_IMAGE_SCRIPT, payload]
    print(f"[publish-local] 调用 post_image.py")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return {
        "ok": r.returncode == 0,
        "stage": "done" if r.returncode == 0 else "post",
        "rc": r.returncode,
        "stdout": (r.stdout or "")[-1500:],
        "stderr": (r.stderr or "")[-1500:],
        "remote_image": images[0] if images else "",
    }


def _publish_remote(text: str, image_path: str = None) -> dict:
    """远程模式: scp 图到 mac mini → ssh 跑 post_image.py。"""
    ts = int(time.time())
    remote_dir = f"{MAC_MINI_REMOTE_TMP}/{ts}"
    rc, _, err = _ssh(f"mkdir -p {remote_dir}", timeout=10)
    if rc != 0:
        return {"ok": False, "stage": "mkdir", "err": err.strip()[:300]}
    images = []
    if image_path:
        local = Path(image_path)
        if not local.exists():
            return {"ok": False, "stage": "image_check", "err": f"本地图不存在: {image_path}"}
        remote_img = f"{remote_dir}/{local.name}"
        rc, _, err = _scp(str(local), remote_img, timeout=180)
        if rc != 0:
            return {"ok": False, "stage": "scp", "err": err.strip()[:300]}
        images = [remote_img]
    payload = json.dumps({"text": text, "images": images}, ensure_ascii=False)
    py = "/usr/bin/env python3"
    cmd = f"{py} {POST_IMAGE_SCRIPT} {json.dumps(payload)}"
    print(f"[publish-remote] 远程执行: {cmd[:120]}...")
    rc, out, err = _ssh(cmd, timeout=300)
    return {
        "ok": rc == 0,
        "stage": "done" if rc == 0 else "post",
        "rc": rc,
        "stdout": out[-1500:] if out else "",
        "stderr": err[-1500:] if err else "",
        "remote_image": images[0] if images else "",
    }


def publish(text: str, image_path: str = None) -> dict:
    """根据 LOCAL_MODE 自动选模式。"""
    return _publish_local(text, image_path) if LOCAL_MODE else _publish_remote(text, image_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: publish.py <文字> [图片路径]"); sys.exit(2)
    text = sys.argv[1]
    image = sys.argv[2] if len(sys.argv) > 2 else None
    r = publish(text, image)
    print(json.dumps(r, ensure_ascii=False, indent=2))
