"""为朋友圈生成配图 - 豆包 Seedream 4.0 (ARK API)。

走 OpenAI 兼容协议 + Bearer Token, 不依赖 AK/SK HMAC 签名,跨机部署稳定。
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

OUT_DIR = Path(__file__).parent.parent / "images"
OUT_DIR.mkdir(exist_ok=True)

ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_BASE = os.getenv("ARK_BASE", "https://ark.cn-beijing.volces.com/api/v3")
ARK_MODEL = os.getenv("ARK_IMAGE_MODEL", "doubao-seedream-4-0-250828")

STYLE_SUFFIX = {
    "cognitive": "极简插画风格,深色背景(墨蓝/深紫/暗红),高对比度,有思考感和锋利感,干净简洁,不要任何文字",
    "case":      "扁平商务插画风格,浅米色背景,有数据/图表/箭头/对话框等暗示『成果』的元素,色调温暖明亮,不要任何文字",
    "persona":   "手绘水彩风格,暖色调(米黄/浅橙/淡棕),有生活感和真实感,可以是物件特写/工作场景/微小细节,不要任何文字",
}


def _call_doubao(prompt: str, out_path: Path,
                  size: str = "1024x1024", timeout: int = 120) -> Path:
    if not ARK_API_KEY:
        raise RuntimeError("缺少 ARK_API_KEY")
    body = {
        "model": ARK_MODEL,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
    }
    r = requests.post(f"{ARK_BASE}/images/generations",
                       headers={"Authorization": f"Bearer {ARK_API_KEY}",
                                "Content-Type": "application/json"},
                       json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"ARK http={r.status_code}: {r.text[:300]}")
    data = r.json()
    if "data" not in data or not data["data"]:
        raise RuntimeError(f"返回缺 data: {str(data)[:300]}")
    url = data["data"][0].get("url")
    if not url:
        raise RuntimeError(f"返回缺 url: {str(data)[:300]}")
    img_bytes = requests.get(url, timeout=60).content
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img_bytes)
    return out_path


def render(type_: str, image_prompt: str, out_path: Path = None) -> Path:
    style = STYLE_SUFFIX.get(type_, STYLE_SUFFIX["cognitive"])
    full_prompt = f"{image_prompt}。{style}"
    seed_part = abs(hash(image_prompt)) & 0xFFFFFF
    out = out_path or OUT_DIR / f"{type_}_{seed_part:06x}.png"
    print(f"[render] {type_} prompt: {full_prompt[:100]}...")
    return _call_doubao(full_prompt, out, size="1024x1024")


if __name__ == "__main__":
    type_ = sys.argv[1] if len(sys.argv) > 1 else "cognitive"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "一只龙虾对着电脑思考的卡通形象"
    print(f"✓ {render(type_, prompt)}")
