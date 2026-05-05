"""为朋友圈生成配图。

每条朋友圈通过即梦 t2i 生成一张视觉化插图(不是文字卡)。
prompt 由 generate.py 中 Claude 输出的 image_prompt 字段提供。
"""
import sys
from pathlib import Path

# 复用 zsxq-publisher 的 t2i 包装
sys.path.insert(0, str(Path.home() / "zsxq-publisher"))
from gen_image import t2i  # noqa: E402

OUT_DIR = Path(__file__).parent.parent / "images"
OUT_DIR.mkdir(exist_ok=True)

# 三种风格的 visual style suffix (附加到 prompt 末尾,统一品牌感)
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


def render(type_: str, image_prompt: str, out_path: Path = None) -> Path:
    """type_ ∈ {cognitive, case, persona}, image_prompt 是 Claude 给的视觉描述。"""
    style = STYLE_SUFFIX.get(type_, STYLE_SUFFIX["cognitive"])
    full_prompt = f"{image_prompt}。{style}"
    seed_part = abs(hash(image_prompt)) & 0xFFFFFF
    out = out_path or OUT_DIR / f"{type_}_{seed_part:06x}.png"
    print(f"[render] {type_} prompt: {full_prompt[:100]}...")
    t2i(full_prompt, str(out), req_key="jimeng_t2i_v40", width=1024, height=1024)
    return out


if __name__ == "__main__":
    type_ = sys.argv[1] if len(sys.argv) > 1 else "cognitive"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "一个龙虾对着电脑思考的卡通形象"
    out = render(type_, prompt)
    print(f"✓ {out}")
