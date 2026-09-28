from app.services.mirror_agent import MirrorAgent


class FakeProvider:
    name = "test"

    def complete_json(self, messages):
        return {
            "reply": "海边可以先看看这两件，选中后我再替你放进镜面。",
            "intent": "show_garments",
            "garment_ids": ["shirt", "invented"],
            "scene": "beach",
        }


def test_mirror_agent_filters_hallucinated_garment_ids():
    reply, action = MirrorAgent(FakeProvider()).reply(
        [{"role": "user", "content": "去海边穿什么？"}],
        [{"id": "shirt", "name": "亚麻衬衫", "category": "top"}],
    )

    assert "海边" in reply
    assert action.type == "show_garments"
    assert action.payload["garment_ids"] == ["shirt"]
    assert action.payload["scene"] == "beach"
