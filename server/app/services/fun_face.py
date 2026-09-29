from __future__ import annotations

import hashlib
from datetime import UTC, datetime

QUESTIONS = [
    {
        "id": "social_energy",
        "text": "今天更接近哪一种状态？",
        "left_label": "想安静一点",
        "right_label": "想和人连接",
    },
    {
        "id": "pace",
        "text": "做决定时，你今天更偏向？",
        "left_label": "慢慢确认",
        "right_label": "先走一步",
    },
    {
        "id": "style",
        "text": "今天希望别人先注意到？",
        "left_label": "柔和可靠",
        "right_label": "鲜明有趣",
    },
]

CAT_BY_INDEX = [
    ("云朵猫", "mist", "wellbeing-mist-cloud"),
    ("月影猫", "moon", "wellbeing-moon-tuxedo"),
    ("晴橘猫", "sun", "wellbeing-sun-orange"),
    ("苔纹猫", "moss", "wellbeing-moss-tabby"),
    ("守夜黑猫", "night", "wellbeing-night-guardian"),
]


def _bounded(value: float) -> int:
    return max(35, min(85, round(50 + (value - 50) * 0.55)))


def build_fun_face_result(user_id: str, answers: list[int], vision: dict) -> dict:
    if len(answers) != 3 or any(value < 0 or value > 100 for value in answers):
        raise ValueError("fun_face_answers_invalid")
    required = ("expression_energy", "lighting_softness", "style_clarity", "eye_contact")
    visual: dict[str, float] = {}
    for name in required:
        value = float(vision[name])
        if not 0 <= value <= 100:
            raise ValueError("fun_face_visual_value_invalid")
        visual[name] = value
    quality = float(vision.get("photo_quality", 0))
    if quality < 45:
        raise ValueError("fun_face_photo_quality_too_low")

    stable_seed = int(
        hashlib.sha256(f"{user_id}:{datetime.now(UTC).date().isoformat()}".encode()).hexdigest()[
            :8
        ],
        16,
    )
    stable = 47 + stable_seed % 7
    warmth = _bounded(answers[0] * 0.46 + visual["expression_energy"] * 0.34 + stable * 0.20)
    presence = _bounded(answers[1] * 0.46 + visual["eye_contact"] * 0.34 + stable * 0.20)
    sparkle = _bounded(answers[2] * 0.46 + visual["style_clarity"] * 0.34 + stable * 0.20)
    ease = _bounded((100 - answers[1]) * 0.35 + visual["lighting_softness"] * 0.45 + stable * 0.20)
    dimensions = {"亲和感": warmth, "在场感": presence, "风格感": sparkle, "松弛感": ease}
    overall = round(sum(dimensions.values()) / len(dimensions))
    cat_index = min(4, max(0, round((overall - 35) / 12.5)))
    cat_type, palette, image_key = CAT_BY_INDEX[cat_index]
    observations = [str(item)[:36] for item in vision.get("observations", [])[:3]]
    card = {
        "family": "fun-face",
        "cat_type": cat_type,
        "title": f"今天的镜面搭档：{cat_type}",
        "subtitle": "每日趣味镜卡 · 仅供娱乐",
        "body": "分数来自你的三项自述与当下照片的可见画面特征，刻意压低极端波动。",
        "palette": palette,
        "image_key": image_key,
    }
    return {
        "overall_score": overall,
        "dimensions": dimensions,
        "observations": observations,
        "explanation": "自述占 46%，可见画面特征占 34%，每日稳定校准占 20%。",
        "notice": ("趣味测试不从脸推断人格、命运、健康或身份；光线、表情和拍摄角度会影响结果。"),
        "card": card,
    }
