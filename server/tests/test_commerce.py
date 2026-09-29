import hashlib
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.providers.commerce import CommerceProduct, TaobaoOpenApiProvider


class FakeCommerceProvider:
    name = "taobao-open-api"

    def resolve_product(self, shared_text: str) -> CommerceProduct:
        assert "123456789" in shared_text
        return CommerceProduct(
            item_id="123456789",
            title="亚麻海边衬衫",
            category="tops",
            image_url="https://img.alicdn.com/product.jpg",
            canonical_url="https://item.taobao.com/item.htm?id=123456789",
            tags=("衬衫", "亚麻"),
        )

    def download_image(self, url: str) -> tuple[bytes, str]:
        output = io.BytesIO()
        Image.new("RGB", (480, 640), (201, 184, 151)).save(output, "JPEG")
        return output.getvalue(), "image/jpeg"


def test_taobao_import_is_private_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "commerce.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    with TestClient(app) as client:
        app.state.commerce_provider = FakeCommerceProvider()
        payload = {"url": "https://item.taobao.com/item.htm?id=123456789"}
        first = client.post("/api/v1/wardrobe/imports/taobao", json=payload)
        second = client.post("/api/v1/wardrobe/imports/taobao", json=payload)
        listed = client.get("/api/v1/wardrobe/garments")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["source_type"] == "taobao"
    assert first.json()["external_item_id"] == "123456789"
    assert len(listed.json()) == 1


def test_top_api_request_uses_expected_md5_signature(monkeypatch):
    captured = {}

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "taobao_tbk_item_info_get_response": {
                    "results": {
                        "n_tbk_item": [
                            {
                                "num_iid": "123456789",
                                "title": "亚麻衬衫",
                                "pict_url": "https://img.alicdn.com/a.jpg",
                                "cat_leaf_name": "衬衫",
                            }
                        ]
                    }
                }
            }

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr("app.providers.commerce._is_public_host", lambda host: True)
    monkeypatch.setattr("app.providers.commerce.httpx.post", fake_post)
    provider = TaobaoOpenApiProvider("app-key", "app-secret")
    product = provider.resolve_product(
        "复制这件衣服 https://item.taobao.com/item.htm?id=123456789"
    )

    params = captured["data"]
    unsigned = {key: value for key, value in params.items() if key != "sign"}
    payload = "app-secret" + "".join(
        f"{key}{unsigned[key]}" for key in sorted(unsigned)
    ) + "app-secret"
    assert params["sign"] == hashlib.md5(payload.encode()).hexdigest().upper()
    assert product.title == "亚麻衬衫"
    assert product.category == "tops"


def test_taobao_provider_rejects_non_taobao_hosts(monkeypatch):
    monkeypatch.setattr("app.providers.commerce._is_public_host", lambda host: True)
    provider = TaobaoOpenApiProvider("app-key", "app-secret")

    try:
        provider.resolve_product("https://example.com/item.htm?id=123456789")
    except ValueError as error:
        assert str(error) == "taobao_link_not_allowed"
    else:
        raise AssertionError("non-Taobao URLs must be rejected")
