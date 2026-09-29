from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
TAOBAO_LINK_HOSTS = {
    "item.taobao.com",
    "detail.tmall.com",
    "m.tb.cn",
    "e.tb.cn",
    "m.taobao.com",
}
IMAGE_HOST_SUFFIXES = (".alicdn.com", ".tbcdn.cn", ".taobaocdn.com")
URL_PATTERN = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


class CommerceImportError(ValueError):
    pass


@dataclass(frozen=True)
class CommerceProduct:
    item_id: str
    title: str
    category: str
    image_url: str
    canonical_url: str
    brand: str | None = None
    tags: tuple[str, ...] = ()


class CommerceProvider(Protocol):
    name: str

    def resolve_product(self, shared_text: str) -> CommerceProduct: ...

    def download_image(self, url: str) -> tuple[bytes, str]: ...


class DisabledCommerceProvider:
    name = "disabled"

    def resolve_product(self, shared_text: str) -> CommerceProduct:
        raise RuntimeError("taobao_open_api_not_configured")

    def download_image(self, url: str) -> tuple[bytes, str]:
        raise RuntimeError("taobao_open_api_not_configured")


def _is_public_host(host: str) -> bool:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        return False
    if not addresses:
        return False
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            return False
    return True


def _extract_url(value: str) -> str:
    match = URL_PATTERN.search(value.strip())
    if not match:
        raise CommerceImportError("taobao_link_invalid")
    return match.group(0).rstrip(".,，。;；!！?？)]】")


def _require_https_host(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or host not in allowed_hosts or parsed.username or parsed.password:
        raise CommerceImportError("taobao_link_not_allowed")
    if parsed.port not in (None, 443) or not _is_public_host(host):
        raise CommerceImportError("taobao_link_not_allowed")
    return host


def _infer_category(*values: str) -> str:
    text = " ".join(values).lower()
    if any(word in text for word in ("连衣裙", "连体", "dress", "jumpsuit")):
        return "one-pieces"
    if any(word in text for word in ("裤", "裙", "shorts", "pants", "jeans", "skirt")):
        return "bottoms"
    return "tops"


class TaobaoOpenApiProvider:
    """Official TOP API adapter. It never scrapes Taobao product pages."""

    name = "taobao-open-api"

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        session: str = "",
        api_method: str = "taobao.tbk.item.info.get",
        endpoint: str = "https://eco.taobao.com/router/rest",
        timeout_seconds: float = 20,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.session = session
        self.api_method = api_method
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def _follow_share_link(self, url: str) -> str:
        _require_https_host(url, TAOBAO_LINK_HOSTS)
        current = url
        for _ in range(5):
            response = httpx.get(current, follow_redirects=False, timeout=self.timeout_seconds)
            if response.status_code not in {301, 302, 303, 307, 308}:
                return current
            location = response.headers.get("location")
            if not location:
                raise CommerceImportError("taobao_link_unresolved")
            current = urljoin(current, location)
            _require_https_host(current, TAOBAO_LINK_HOSTS)
        raise CommerceImportError("taobao_link_too_many_redirects")

    @staticmethod
    def _item_id(url: str) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        candidates = query.get("id", []) + query.get("itemId", []) + query.get("item_id", [])
        path_match = re.search(r"/(\d{6,20})(?:\.htm)?(?:/|$)", parsed.path)
        if path_match:
            candidates.append(path_match.group(1))
        for candidate in candidates:
            if re.fullmatch(r"\d{6,20}", candidate):
                return candidate
        raise CommerceImportError("taobao_item_id_missing")

    def _signed_params(self, item_id: str) -> dict[str, str]:
        params = {
            "method": self.api_method,
            "app_key": self.app_key,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": "json",
            "v": "2.0",
            "sign_method": "md5",
            "num_iids": item_id,
            "platform": "2",
        }
        if self.session:
            params["session"] = self.session
        payload = (
            self.app_secret
            + "".join(f"{key}{params[key]}" for key in sorted(params))
            + self.app_secret
        )
        params["sign"] = hashlib.md5(payload.encode("utf-8")).hexdigest().upper()
        return params

    def resolve_product(self, shared_text: str) -> CommerceProduct:
        original = _extract_url(shared_text)
        resolved = (
            self._follow_share_link(original)
            if urlparse(original).hostname in {"m.tb.cn", "e.tb.cn"}
            else original
        )
        _require_https_host(resolved, TAOBAO_LINK_HOSTS)
        item_id = self._item_id(resolved)
        response = httpx.post(
            self.endpoint,
            data=self._signed_params(item_id),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if "error_response" in data:
            message = data["error_response"].get("sub_msg") or data["error_response"].get("msg")
            raise CommerceImportError(f"taobao_api_error:{message or 'unknown'}")
        root_key = self.api_method.replace(".", "_") + "_response"
        root = data.get(root_key, {})
        results = root.get("results", {})
        items = results.get("n_tbk_item") or results.get("item") or []
        if isinstance(items, dict):
            items = [items]
        if not items:
            raise CommerceImportError("taobao_product_not_available")
        item = items[0]
        title = str(item.get("title") or "").strip()
        image_url = str(item.get("pict_url") or item.get("pic_url") or "").strip()
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        if not title or not image_url:
            raise CommerceImportError("taobao_product_incomplete")
        category_name = str(item.get("cat_leaf_name") or item.get("cat_name") or "")
        canonical_url = str(item.get("item_url") or resolved)
        return CommerceProduct(
            item_id=item_id,
            title=title[:128],
            category=_infer_category(title, category_name),
            image_url=image_url,
            canonical_url=canonical_url,
            brand=(str(item.get("brand_name") or "").strip() or None),
            tags=tuple(value for value in (category_name,) if value),
        )

    def download_image(self, url: str) -> tuple[bytes, str]:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (
            parsed.scheme != "https"
            or not any(host.endswith(suffix) for suffix in IMAGE_HOST_SUFFIXES)
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or not _is_public_host(host)
        ):
            raise CommerceImportError("taobao_image_host_not_allowed")
        response = httpx.get(url, follow_redirects=False, timeout=self.timeout_seconds)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise CommerceImportError("taobao_image_invalid_type")
        if len(response.content) > MAX_PRODUCT_IMAGE_BYTES:
            raise CommerceImportError("taobao_image_too_large")
        return response.content, content_type
