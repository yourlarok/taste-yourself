from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    load_dotenv(ROOT / ".env")
    failures: list[str] = []

    project = json.loads((ROOT / "project.config.json").read_text(encoding="utf-8"))
    if project.get("appid") in {None, "", "touristappid"}:
        failures.append("project.config.json 仍使用 touristappid")

    mini_config = (ROOT / "miniprogram" / "env.js").read_text(encoding="utf-8")
    if "useMock: true" in mini_config:
        failures.append("miniprogram/env.js 仍启用演示数据")
    if "127.0.0.1" in mini_config or "your-server.example.com" in mini_config:
        failures.append("miniprogram/env.js 仍使用本地或示例 API 地址")

    required = [
        "AUTH_TOKEN_SECRET",
        "WECHAT_APP_ID",
        "WECHAT_APP_SECRET",
        "PUBLIC_DOMAIN",
    ]
    for name in required:
        if not os.getenv(name):
            failures.append(f"缺少环境变量 {name}")

    if os.getenv("APP_ENV") != "production":
        failures.append("APP_ENV 必须为 production")
    if len(os.getenv("AUTH_TOKEN_SECRET", "")) < 32:
        failures.append("AUTH_TOKEN_SECRET 必须至少 32 个字符")
    if os.getenv("AUTH_TOKEN_SECRET", "").startswith("replace-"):
        failures.append("AUTH_TOKEN_SECRET 仍是示例值")
    tryon_provider = os.getenv("TRYON_PROVIDER")
    if tryon_provider not in {"fashn-http", "fashn-api"}:
        failures.append("TRYON_PROVIDER 必须为 fashn-api 或 fashn-http")
    elif tryon_provider == "fashn-api" and not os.getenv("FASHN_API_KEY"):
        failures.append("缺少环境变量 FASHN_API_KEY")
    elif tryon_provider == "fashn-http":
        if not os.getenv("FASHN_WORKER_URL"):
            failures.append("缺少环境变量 FASHN_WORKER_URL")
        if not os.getenv("FASHN_WORKER_TOKEN"):
            failures.append("缺少环境变量 FASHN_WORKER_TOKEN")
    if os.getenv("REALTIME_PROVIDER") != "http":
        failures.append("REALTIME_PROVIDER 必须为 http")
    if not os.getenv("REALTIME_SESSION_URL"):
        failures.append("缺少环境变量 REALTIME_SESSION_URL")
    if not os.getenv("REALTIME_PROVIDER_TOKEN"):
        failures.append("缺少环境变量 REALTIME_PROVIDER_TOKEN")
    if os.getenv("BODY_SCAN_PROVIDER") != "http":
        failures.append("BODY_SCAN_PROVIDER 必须为 http")
    if not os.getenv("BODY_SCAN_WORKER_URL"):
        failures.append("缺少环境变量 BODY_SCAN_WORKER_URL")
    if os.getenv("CONTENT_SAFETY_PROVIDER") != "http":
        failures.append("CONTENT_SAFETY_PROVIDER 必须为 http")
    if not os.getenv("CONTENT_SAFETY_URL"):
        failures.append("缺少环境变量 CONTENT_SAFETY_URL")
    positive_integers = (
        "STATIC_DAILY_LIMIT",
        "REALTIME_DAILY_LIMIT",
        "PERSON_IMAGE_RETENTION_DAYS",
        "TRYON_RESULT_RETENTION_DAYS",
    )
    for name in positive_integers:
        try:
            if int(os.getenv(name, "0")) <= 0:
                raise ValueError
        except ValueError:
            failures.append(f"{name} 必须为正整数")

    public_domain = os.getenv("PUBLIC_DOMAIN", "")
    parsed = urlparse(public_domain if "://" in public_domain else f"https://{public_domain}")
    if not parsed.hostname or parsed.hostname in {"example.com", "api.example.com"}:
        failures.append("PUBLIC_DOMAIN 必须是真实域名")

    if failures:
        print("发布前检查失败：")
        for item in failures:
            print(f"- {item}")
        return 1

    print("发布前静态配置检查通过。仍需完成真机、隐私与体验版人工验收。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
