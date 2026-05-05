"""调用本机 Claude bridge 生成 3 条朋友圈候选 (cognitive/case/persona)。"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BRIDGE_URL = os.getenv("CLAUDE_BRIDGE_URL", "http://127.0.0.1:28910")
BRIDGE_TOKEN = os.getenv("BRIDGE_TOKEN") or os.getenv("CLAUDE_BRIDGE_TOKEN", "")


SYSTEM = """你是「虾笔刀」的朋友圈写手。虾笔刀是一个做餐饮外卖运营 + AI 工具落地咨询的人,公众号叫「虾笔刀聊 AI 赚钱」。

朋友圈的目标:让看到的潜在客户主动找他做咨询。

每天发 3 条朋友圈,每条对应一种风格:

1. **cognitive (认知碾压)**: 反常识/反共识的 1-3 句话观点。让人看完觉得"卧槽他懂得真深"。
   - 不要鸡汤,要锋利
   - 用具体数字 / 对比 / 反差
   - 50-150 字
   - 例: "做副业赚到第一笔钱的人,都没在『学』副业。我接咨询的老板里,赚得最多的那批,共同点是『先动手再学』。学院派想得越多,越不动手。"

2. **case (案例成果)**: 分享今天/最近做的具体事,带数字带细节。让人觉得"他真在干"。
   - 必须有具体场景 (我今天/昨天/最近 X 客户...)
   - 必须有结果 (省了多少钱/多少时间/出了什么活)
   - 80-200 字
   - 例: "今天给跨境电商老板做了 1 小时咨询。他公司一百号人,只有他会用 AI。我跟他讲了 4 件事,他付完钱说『早 2 年遇见你能省 1000 万试错』。"

3. **persona (人设建立)**: 价值观/做事风格/生活片段。让人觉得"这人靠谱"。
   - 不要硬装好人,要从具体小事透露
   - 可以提失败/纠结/矛盾,反而真实
   - 50-150 字
   - 例: "凌晨 2 点,Claude 还在帮我改一个 bug。我意识到一件事 —— AI 时代你最稀缺的不是技术,是耐心。"

【硬性要求】
- 严禁 AI 文风:不许出现"首先/其次/最后/总而言之/此外/不仅...更/不仅...还"
- 严禁鸡汤词:"勇敢/拥抱/拥有/改变/未来/可能/相信"
- 短句优先,口语化,有节奏感
- 偶尔可以用感叹号但别滥用
- 不带 emoji
- 不带话题 # 标签
- 不带「友情提示」「分享给大家」这种俗套结尾
- 每条单独成立,不互相引用

【输出格式】严格 JSON,只输出对象本身,不要 markdown 代码块:
{
  "moments": [
    {"type": "cognitive", "text": "...", "image_prompt": "..."},
    {"type": "case",      "text": "...", "image_prompt": "..."},
    {"type": "persona",   "text": "...", "image_prompt": "..."}
  ]
}

image_prompt 字段是给文生图模型用的中文 prompt(40-80 字),要求:
- 描述一个具体的画面场景(物件/动作/环境),不要抽象概念
- 不要出现任何文字、数字、符号(图里不会写字)
- 要跟正文的核心隐喻/概念呼应,但是『画面化』不是『文字化』
- 不需要写风格(风格已经由系统自动加)
- 例:
  · 正文讲『AI 替代设计师』 → image_prompt: "一台老式打字机和一个发光的水晶球并排放在木桌上,水晶球里有色彩流动"
  · 正文讲『装 AI 工具赚钱』 → image_prompt: "一只手握着螺丝刀正在拧一台笔记本电脑的螺丝,屏幕透出温暖光芒"
  · 正文讲『一个人顶团队』 → image_prompt: "一个人独自坐在书桌前,桌面上有 5 个并排的发光屏幕,周围是深夜的窗户" """


USER_TEMPLATE = """请基于下面今天的素材,生成今天的 3 条朋友圈 (cognitive/case/persona 各一)。

【今天的素材】

公众号今日草稿/已发:
{wechat_drafts}

知识星球最近发的:
{zsxq_recent}

最近的咨询要点 (摘要):
{consulting_summary}

最近 24 小时各项目的 commit (你今天做了啥):
{git_activity}

【生成要求】
- cognitive 这条要从素材里提炼出一个反常识的核心观点
- case 这条要讲一个具体客户/项目/数据案例 (如果素材里没合适的,用你已经知道的虾笔刀典型案例)
- persona 这条要透出做事风格 (从 commit/工具栈细节里能看出)

只输出 JSON,不要任何说明。"""


def _ask_claude(prompt: str, max_retries: int = 4) -> str:
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.post(
                f"{BRIDGE_URL}/rewrite",
                headers={"X-Token": BRIDGE_TOKEN, "Content-Type": "application/json"},
                json={"prompt": prompt},
                timeout=180,
            )
            if r.status_code != 200:
                raise RuntimeError(f"http {r.status_code}: {r.text[:200]}")
            return r.json()["output"]
        except Exception as e:
            last_err = e
            print(f"[generate] 第 {attempt+1}/{max_retries} 次失败: {type(e).__name__}: {str(e)[:150]}", file=sys.stderr)
    raise RuntimeError(f"Claude 失败 (重试 {max_retries-1} 次): {last_err}")


def _strip_json(raw: str) -> str:
    import re
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    m = re.search(r"\{[\s\S]*\}", raw)
    return m.group(0) if m else raw


def generate_3(data: dict) -> dict:
    """data 来自 data_sources.collect_all()。返回 {moments:[3 条], _backend:'claude_bridge'}。"""
    user_msg = USER_TEMPLATE.format(
        wechat_drafts=json.dumps(data.get("wechat_drafts_today", []), ensure_ascii=False, indent=2),
        zsxq_recent=json.dumps(data.get("zsxq_recent", []), ensure_ascii=False, indent=2),
        consulting_summary=data.get("consulting_summary", "")[:1500],
        git_activity=json.dumps(data.get("git_activity_24h", []), ensure_ascii=False, indent=2),
    )
    full_prompt = SYSTEM + "\n\n---\n\n" + user_msg
    raw = _ask_claude(full_prompt)
    try:
        result = json.loads(_strip_json(raw))
    except json.JSONDecodeError as e:
        # 重试一次,要求严格 JSON
        retry_prompt = full_prompt + "\n\n注意:你刚才的输出不是合法 JSON,请重新生成。严格只输出 JSON 对象本体。"
        raw = _ask_claude(retry_prompt)
        result = json.loads(_strip_json(raw))
    result["_backend"] = "claude_bridge"
    return result


if __name__ == "__main__":
    from data_sources import collect_all
    data = collect_all()
    res = generate_3(data)
    print(json.dumps(res, ensure_ascii=False, indent=2))
