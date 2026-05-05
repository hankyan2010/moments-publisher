"""发布执行: scp 图到 mac mini → ssh 跑 post_image.py → 拿回 OCR 验证结果。"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

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


def publish(text: str, image_path: str = None) -> dict:
    """完整发布流程: 上传图 → 远程发 → 收集结果。
    返回 dict {ok, remote_image, output, err}。"""
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
    # python3 在 mac mini 上路径
    py = "/usr/bin/env python3"
    cmd = f"{py} {POST_IMAGE_SCRIPT} {json.dumps(payload)}"

    print(f"[publish] 远程执行: {cmd[:120]}...")
    rc, out, err = _ssh(cmd, timeout=300)
    success = (rc == 0)

    return {
        "ok": success,
        "stage": "done" if success else "post",
        "rc": rc,
        "stdout": out[-1500:] if out else "",
        "stderr": err[-1500:] if err else "",
        "remote_image": images[0] if images else "",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: publish.py <文字> [图片路径]"); sys.exit(2)
    text = sys.argv[1]
    image = sys.argv[2] if len(sys.argv) > 2 else None
    r = publish(text, image)
    print(json.dumps(r, ensure_ascii=False, indent=2))
