from __future__ import annotations

from app.domain.mirror import MirrorAction
from app.providers.llm import LLMProvider

ALLOWED_INTENTS = {
    "chat",
    "open_tryon",
    "show_garments",
    "open_wardrobe",
    "start_fun_face",
    "start_wellbeing",
    "open_atlas",
}

SYSTEM_PROMPT = """你是微信小程序“猫猫魔镜”中的魔镜 Agent。你的语气温暖、机灵、克制，不装神秘，
不使用医疗诊断或宿命论。你负责理解用户要聊天、试衣、找衣服、打开衣橱、进行趣味面相、进行心理
幸福感自评或打开猫猫图鉴。只输出 JSON：{"reply":"不超过80字的中文回复","intent":"允许的意图",
"garment_ids":[],"scene":""}。允许的意图为 chat/open_tryon/show_garments/open_wardrobe/
start_fun_face/start_wellbeing/open_atlas。涉及面相时说明它只是趣味视觉卡，不从脸推断人格、健康、种族或命运。
涉及心理状态时说明是自评引导，不是诊断。只有给定衣服列表中的 id 才能放入 garment_ids。"""

SYSTEM_PROMPT += """找衣服时遵守这些规则：用户说“我的衣服、衣橱里、帮我取”时，优先 source=wardrobe；
用户明确说预设或想看灵感时才优先 source=preset。根据场景、版型、材质、体型标签解释匹配点，但不打分、
不替用户作购买决定。若性别适用、体型或场景是决定性条件而用户没有提供，先追问一个最关键问题，
此时 intent=chat 且 garment_ids 为空。用户提到海边时 scene=beach，
并优先 breathable/relaxed 标签。"""

SCENES = {"beach", "city", "cafe", "garden", "studio", "snow", "sunset"}


class MirrorAgent:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def reply(
        self,
        history: list[dict[str, str]],
        garments: list[dict[str, str]],
    ) -> tuple[str, MirrorAction]:
        inventory = "\n".join(
            f"- {item['id']}: {item['name']}; 类别={item.get('category', '未知')}; "
            f"来源={item.get('source', 'preset')}; 适用={item.get('audience', 'unknown')}; "
            f"体型标签={item.get('body_types', '')}; 场景={item.get('occasions', '')}; "
            f"风格={item.get('tags', '')}; 材质={item.get('material', '')}; "
            f"版型={item.get('silhouette', '')}"
            for item in garments[:80]
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"当前可用衣服：\n{inventory or '暂无'}"},
            *history,
        ]
        data = self.provider.complete_json(messages)
        reply = str(data.get("reply", "")).strip()
        intent = str(data.get("intent", "chat"))
        if not reply or intent not in ALLOWED_INTENTS:
            raise ValueError("mirror_agent_invalid_response")
        valid_ids = {item["id"] for item in garments}
        selected = [str(item) for item in data.get("garment_ids", []) if str(item) in valid_ids][
            :12
        ]
        payload: dict[str, str | list[str] | bool] = {}
        if selected:
            payload["garment_ids"] = selected
        scene = str(data.get("scene", ""))
        if scene in SCENES:
            payload["scene"] = scene
        return reply, MirrorAction(type=intent, payload=payload)
