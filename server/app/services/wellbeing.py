from __future__ import annotations

from app.domain.mirror import WellbeingAssessmentCreate

QUESTIONS = [
    {"id": "cheerful", "text": "过去两周，我感到心情愉快、精神不错"},
    {"id": "calm", "text": "过去两周，我感到平静、放松"},
    {"id": "active", "text": "过去两周，我感到有活力"},
    {"id": "rested", "text": "过去两周，我醒来时觉得清醒、休息充分"},
    {"id": "interested", "text": "过去两周，我的日常生活中有令我感兴趣的事情"},
]

FACTOR_LABELS = {
    "sleep": "睡眠或作息可能正在消耗你的精力",
    "workload": "近期任务负荷可能偏高",
    "relationships": "关系与沟通压力可能占用了不少注意力",
    "physical": "身体不适可能影响了情绪和精力",
    "uncertainty": "持续的不确定感可能让你难以放松",
    "none": "暂时没有明确的单一诱因",
}

STATE_CARDS = {
    "steady": {
        "cat_type": "晴橘猫",
        "title": "今天的你，底色很稳",
        "subtitle": "晴橘猫 · 稳定陪伴",
        "body": "保持让你恢复精力的小习惯，也给偶尔的低落留一点空间。",
        "palette": "sun",
        "image_key": "wellbeing-sun-orange",
    },
    "tired": {
        "cat_type": "云朵猫",
        "title": "电量有点低，先慢一点",
        "subtitle": "云朵猫 · 轻柔复原",
        "body": "你可能需要的不是更用力，而是一段可执行的恢复时间。",
        "palette": "mist",
        "image_key": "wellbeing-mist-cloud",
    },
    "strained": {
        "cat_type": "苔纹猫",
        "title": "压力已经有了重量",
        "subtitle": "苔纹猫 · 稳住节奏",
        "body": "把问题缩小到今天能处理的一步，并让可信任的人知道你的状态。",
        "palette": "moss",
        "image_key": "wellbeing-moss-tabby",
    },
    "low": {
        "cat_type": "月影猫",
        "title": "这段时间并不轻松",
        "subtitle": "月影猫 · 安静守夜",
        "body": "持续低落值得被认真对待。可以从联系可信任的人或专业支持开始。",
        "palette": "moon",
        "image_key": "wellbeing-moon-tuxedo",
    },
    "urgent": {
        "cat_type": "守夜黑猫",
        "title": "现在先保证你的安全",
        "subtitle": "守夜黑猫 · 即刻陪伴",
        "body": "请立刻联系身边可信任的人、当地急救或心理危机干预服务，不要独处。",
        "palette": "night",
        "image_key": "wellbeing-night-guardian",
    },
}


def assess_wellbeing(payload: WellbeingAssessmentCreate) -> dict:
    score = sum(payload.answers) * 4
    if payload.immediate_danger:
        state = "urgent"
    elif score >= 76:
        state = "steady"
    elif score >= 52:
        state = "tired"
    elif score >= 32:
        state = "strained"
    else:
        state = "low"

    labels = {
        "steady": "近期心理幸福感较稳定",
        "tired": "近期可能有些疲惫",
        "strained": "近期压力感可能较明显",
        "low": "近期心理幸福感偏低",
        "urgent": "需要立即获得现实中的支持",
    }
    factors = [FACTOR_LABELS[item] for item in payload.contributors]
    if not factors:
        factors = ["仅凭这次自评无法判断原因，可以继续观察睡眠、压力与身体状态"]

    if state == "urgent":
        steps = [
            "现在就联系一位可信任的人并说明你需要陪伴",
            "远离可能伤害自己的物品和危险地点",
            "联系当地急救电话或心理危机干预服务",
        ]
    elif state == "low":
        steps = [
            "今天向一位可信任的人说出真实状态",
            "若状态持续或影响生活，尽快联系心理咨询师或精神科/心理科",
            "把吃饭、喝水、睡眠和短时间活动作为今天的最低任务",
        ]
    elif state == "strained":
        steps = [
            "从压力清单中只选一件今天能完成的小事",
            "安排至少二十分钟不处理任务的恢复时间",
            "若连续两周没有改善，考虑寻求专业支持",
        ]
    elif state == "tired":
        steps = [
            "为今晚设定一个具体的停止工作时间",
            "做一次十分钟的散步、拉伸或安静休息",
            "三天后回看状态是否恢复",
        ]
    else:
        steps = [
            "保留一个让你恢复精力的日常习惯",
            "记录最近帮助你稳定的一个人或一件事",
            "状态明显变化时可以再次测试",
        ]

    card = {"family": "wellbeing", **STATE_CARDS[state]}
    return {
        "score": score,
        "state": state,
        "state_label": labels[state],
        "possible_factors": factors,
        "next_steps": steps,
        "notice": (
            "这是基于 WHO-5 结构的自我状态整理，不是医学诊断；分数只反映过去两周的自我感受。"
        ),
        "card": card,
    }
