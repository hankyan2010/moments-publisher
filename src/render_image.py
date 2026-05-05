"""为朋友圈生成配图,即梦 t2i (火山引擎)。"""
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from volcengine.visual.VisualService import VisualService

OUT_DIR = Path(__file__).parent.parent / "images"
OUT_DIR.mkdir(exist_ok=True)

VOLC_AK = os.getenv("VOLC_AK")
VOLC_SK = os.getenv("VOLC_SK")

# 三种风格
STYLE_SUFFIX = {
    "cognitive": (
        "极简插画风格,深色背景(墨蓝/深紫/暗红),高对比度,有思考感和锋利感,"
        "干净简洁,不要任何文字"
    ),
    "case": (
        "扁平商务插画风格,浅米色背景,有数据/图表/箭头/对话框等暗示『成果』的元素,"
        "色调温暖明亮,不要任何文字"
    ),
    "persona": (
        "手绘水彩风格,暖色调(米黄/浅橙/淡棕),有生活感和真实感,"
        "可以是物件特写/工作场景/微小细节,不要任何文字"
    ),
}


def _t2i(prompt: str, out_path: Path, req_key: str = "jimeng_t2i_v40",
         width: int = 1024, height: int = 1024, max_wait: int = 120) -> Path:
    if not (VOLC_AK and VOLC_SK):
        raise RuntimeError("缺少 VOLC_AK / VOLC_SK 环境变量")
    svc = VisualService()
    svc.set_ak(VOLC_AK); svc.set_sk(VOLC_SK)
    form = {"req_key": req_key, "prompt": prompt,
            "width": width, "height": height, "return_url": True}
    submit = None
    for attempt in range(12):
        try:
            submit = svc.cv_sync2async_submit_task(form)
            if isinstance(submit, dict) and submit.get("code") == 10000:
                break
            if isinstance(submit, dict) and ("50430" in str(submit) or "Concurrent" in str(submit)):
                time.sleep(5 + attempt * 3); continue
            raise RuntimeError(f"提交失败: {submit}")
        except Exception as e:
            if "50430" in str(e) or "Concurrent" in str(e):
                print(f"  并发限制,{5 + attempt * 3}s 后重试 ({attempt+1}/12)", flush=True)
                time.sleep(5 + attempt * 3); continue
            raise
    else:
        raise RuntimeError("12 次提交均触发并发限制")

    task_id = submit["data"]["task_id"]
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(3)
        r = svc.cv_sync2async_get_result({
            "req_key": req_key, "task_id": task_id,
            "req_json": json.dumps({"return_url": True}),
        })
        st = (r.get("data") or {}).get("status")
        if st in ("done", "success"):
            data = r["data"]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if data.get("binary_data_base64"):
                out_path.write_bytes(base64.b64decode(data["binary_data_base64"][0]))
            elif data.get("image_urls"):
                out_path.write_bytes(requests.get(data["image_urls"][0], timeout=60).content)
            else:
                raise RuntimeError(f"返回结构异常: {data}")
            return out_path
        if "fail" in str(st).lower() or st == "not_found":
            raise RuntimeError(f"任务失败: {r}")
    raise RuntimeError("超时")


def render(type_: str, image_prompt: str, out_path: Path = None) -> Path:
    style = STYLE_SUFFIX.get(type_, STYLE_SUFFIX["cognitive"])
    full_prompt = f"{image_prompt}。{style}"
    seed_part = abs(hash(image_prompt)) & 0xFFFFFF
    out = out_path or OUT_DIR / f"{type_}_{seed_part:06x}.png"
    print(f"[render] {type_} prompt: {full_prompt[:100]}...")
    return _t2i(full_prompt, out, req_key="jimeng_t2i_v40", width=1024, height=1024)


if __name__ == "__main__":
    type_ = sys.argv[1] if len(sys.argv) > 1 else "cognitive"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "一个龙虾对着电脑思考的卡通形象"
    print(f"✓ {render(type_, prompt)}")
