from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.mirror_routes import router as mirror_router
from app.api.routes import router
from app.providers.body_scan import (
    BodygramPlatformProvider,
    DisabledBodyScanProvider,
    HttpBodyScanProvider,
)
from app.providers.content_safety import HttpContentSafetyProvider, MockContentSafetyProvider
from app.providers.llm import DisabledLLMProvider, OpenAICompatibleLLMProvider
from app.providers.tryon import FashnApiTryOnProvider, FashnHttpTryOnProvider, MockTryOnProvider
from app.repositories.body_scans import BodyScanRepository
from app.repositories.experience import ExperienceRepository
from app.repositories.feedback import FeedbackRepository
from app.repositories.fit_profiles import FitProfileRepository
from app.repositories.mirror import MirrorRepository
from app.repositories.quota import QuotaRepository
from app.repositories.users import UserRepository
from app.repositories.wardrobe import WardrobeRepository
from app.services.auth import TokenService, WechatAuthService
from app.services.image_storage import LocalImageStorage
from app.services.media_signing import MediaUrlSigner
from app.services.mirror_agent import MirrorAgent
from app.services.privacy import PrivacyService
from app.services.retention import RetentionService


def validate_production_environment(app_env: str) -> None:
    if app_env != "production":
        return
    required_values = {
        "WECHAT_APP_ID": os.getenv("WECHAT_APP_ID", ""),
        "WECHAT_APP_SECRET": os.getenv("WECHAT_APP_SECRET", ""),
        "CONTENT_SAFETY_URL": os.getenv("CONTENT_SAFETY_URL", ""),
        "MIRROR_LLM_BASE_URL": os.getenv("MIRROR_LLM_BASE_URL", ""),
        "MIRROR_LLM_API_KEY": os.getenv("MIRROR_LLM_API_KEY", ""),
        "MIRROR_LLM_MODEL": os.getenv("MIRROR_LLM_MODEL", ""),
        "MIRROR_VISION_MODEL": os.getenv("MIRROR_VISION_MODEL", ""),
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise RuntimeError("Missing production configuration: " + ", ".join(missing))
    tryon_provider = os.getenv("TRYON_PROVIDER", "")
    if tryon_provider not in {"fashn-http", "fashn-api"}:
        raise RuntimeError("Production forbids mock or disabled providers: TRYON_PROVIDER")
    if tryon_provider == "fashn-http" and not os.getenv("FASHN_WORKER_URL"):
        raise RuntimeError("Missing production configuration: FASHN_WORKER_URL")
    if tryon_provider == "fashn-api" and not os.getenv("FASHN_API_KEY"):
        raise RuntimeError("Missing production configuration: FASHN_API_KEY")
    if not os.getenv("DECART_API_KEY"):
        raise RuntimeError("Missing production configuration: DECART_API_KEY")
    selections = {
        "REALTIME_PROVIDER": (os.getenv("REALTIME_PROVIDER", ""), {"decart-realtime"}),
        "CONTENT_SAFETY_PROVIDER": (os.getenv("CONTENT_SAFETY_PROVIDER", ""), {"http"}),
    }
    invalid = [name for name, (actual, expected) in selections.items() if actual not in expected]
    if invalid:
        raise RuntimeError("Production forbids mock or disabled providers: " + ", ".join(invalid))
    body_provider = os.getenv("BODY_SCAN_PROVIDER", "")
    if body_provider == "bodygram-platform":
        missing_bodygram = [
            name
            for name in ("BODYGRAM_ORG_ID", "BODYGRAM_API_KEY")
            if not os.getenv(name)
        ]
        if missing_bodygram:
            raise RuntimeError(
                "Missing production configuration: " + ", ".join(missing_bodygram)
            )
    elif body_provider == "http" and not os.getenv("BODY_SCAN_WORKER_URL"):
        raise RuntimeError("Missing production configuration: BODY_SCAN_WORKER_URL")
    elif body_provider != "http":
        raise RuntimeError("Production forbids mock or disabled providers: BODY_SCAN_PROVIDER")


async def run_retention_loop(
    service: RetentionService,
    person_days: int,
    result_days: int,
) -> None:
    while True:
        await asyncio.sleep(6 * 60 * 60)
        await asyncio.to_thread(service.purge, person_days, result_days)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_path = Path(os.getenv("DATABASE_PATH", "data/taste-yourself.db"))
    media_root = Path(os.getenv("MEDIA_ROOT", "data/media"))
    app_env = os.getenv("APP_ENV", "development")
    auth_secret = os.getenv("AUTH_TOKEN_SECRET", "development-only-secret-change-me")
    if app_env == "production" and len(auth_secret) < 32:
        raise RuntimeError("AUTH_TOKEN_SECRET must contain at least 32 characters in production")
    validate_production_environment(app_env)
    app.state.feedback_repository = FeedbackRepository(database_path)
    app.state.mirror_repository = MirrorRepository(database_path)
    app.state.fit_profile_repository = FitProfileRepository(database_path)
    app.state.quota_repository = QuotaRepository(database_path)
    app.state.static_daily_limit = int(os.getenv("STATIC_DAILY_LIMIT", "20"))
    app.state.realtime_daily_limit = int(os.getenv("REALTIME_DAILY_LIMIT", "3"))
    app.state.experience_repository = ExperienceRepository(database_path)
    app.state.body_scan_repository = BodyScanRepository(database_path)
    app.state.wardrobe_repository = WardrobeRepository(database_path)
    app.state.user_repository = UserRepository(database_path)
    app.state.app_env = app_env
    app.state.token_service = TokenService(auth_secret)
    app.state.media_signer = MediaUrlSigner(auth_secret)
    app.state.privacy_service = PrivacyService(database_path, media_root)
    person_retention_days = int(os.getenv("PERSON_IMAGE_RETENTION_DAYS", "7"))
    result_retention_days = int(os.getenv("TRYON_RESULT_RETENTION_DAYS", "30"))
    if person_retention_days <= 0 or result_retention_days <= 0:
        raise RuntimeError("Media retention days must be positive integers")
    app.state.retention_service = RetentionService(database_path, media_root)
    app.state.retention_service.purge(
        person_days=person_retention_days,
        result_days=result_retention_days,
    )
    retention_task = asyncio.create_task(
        run_retention_loop(
            app.state.retention_service,
            person_retention_days,
            result_retention_days,
        )
    )
    wechat_app_id = os.getenv("WECHAT_APP_ID", "")
    wechat_app_secret = os.getenv("WECHAT_APP_SECRET", "")
    app.state.decart_api_key = os.getenv("DECART_API_KEY", "")
    app.state.realtime_web_origin = os.getenv(
        "REALTIME_WEB_ORIGIN", "https://tryon.xuefeitryon.com"
    )
    app.state.wechat_auth_service = (
        WechatAuthService(
            wechat_app_id,
            wechat_app_secret,
            app.state.user_repository,
            app.state.token_service,
        )
        if wechat_app_id and wechat_app_secret
        else None
    )
    storage = LocalImageStorage(media_root)
    app.state.image_storage = storage
    llm_api_key = os.getenv("MIRROR_LLM_API_KEY", "")
    llm_base_url = os.getenv("MIRROR_LLM_BASE_URL", "")
    llm_model = os.getenv("MIRROR_LLM_MODEL", "")
    if llm_api_key and llm_base_url and llm_model:
        llm_provider = OpenAICompatibleLLMProvider(llm_base_url, llm_api_key, llm_model)
    else:
        llm_provider = DisabledLLMProvider()
    app.state.mirror_agent = MirrorAgent(llm_provider)
    vision_model = os.getenv("MIRROR_VISION_MODEL", "")
    if llm_api_key and llm_base_url and vision_model:
        app.state.mirror_vision_provider = OpenAICompatibleLLMProvider(
            llm_base_url, llm_api_key, vision_model
        )
    else:
        app.state.mirror_vision_provider = DisabledLLMProvider()
    provider_name = os.getenv("TRYON_PROVIDER", "mock")
    if provider_name == "mock":
        app.state.tryon_provider = MockTryOnProvider()
    elif provider_name == "fashn-http":
        worker_url = os.getenv("FASHN_WORKER_URL")
        if not worker_url:
            raise RuntimeError("FASHN_WORKER_URL is required for TRYON_PROVIDER=fashn-http")
        app.state.tryon_provider = FashnHttpTryOnProvider(
            base_url=worker_url,
            token=os.getenv("FASHN_WORKER_TOKEN", ""),
            storage=storage,
        )
    elif provider_name == "fashn-api":
        api_key = os.getenv("FASHN_API_KEY")
        if not api_key:
            raise RuntimeError("FASHN_API_KEY is required for TRYON_PROVIDER=fashn-api")
        app.state.tryon_provider = FashnApiTryOnProvider(
            api_key=api_key,
            base_url=os.getenv("FASHN_API_BASE_URL", "https://api.fashn.ai/v1"),
            storage=storage,
        )
    else:
        raise RuntimeError(f"Unsupported TRYON_PROVIDER: {provider_name}")
    body_provider_name = os.getenv("BODY_SCAN_PROVIDER", "disabled")
    if body_provider_name == "disabled":
        app.state.body_scan_provider = DisabledBodyScanProvider()
    elif body_provider_name == "http":
        body_worker_url = os.getenv("BODY_SCAN_WORKER_URL")
        if not body_worker_url:
            raise RuntimeError("BODY_SCAN_WORKER_URL is required for BODY_SCAN_PROVIDER=http")
        app.state.body_scan_provider = HttpBodyScanProvider(
            body_worker_url,
            os.getenv("BODY_SCAN_WORKER_TOKEN", ""),
        )
    elif body_provider_name == "bodygram-platform":
        organization_id = os.getenv("BODYGRAM_ORG_ID", "")
        api_key = os.getenv("BODYGRAM_API_KEY", "")
        if not organization_id or not api_key:
            raise RuntimeError(
                "BODYGRAM_ORG_ID and BODYGRAM_API_KEY are required for "
                "BODY_SCAN_PROVIDER=bodygram-platform"
            )
        app.state.body_scan_provider = BodygramPlatformProvider(organization_id, api_key)
    else:
        raise RuntimeError(f"Unsupported BODY_SCAN_PROVIDER: {body_provider_name}")
    safety_provider_name = os.getenv("CONTENT_SAFETY_PROVIDER", "mock")
    if safety_provider_name == "mock":
        app.state.content_safety_provider = MockContentSafetyProvider()
    elif safety_provider_name == "http":
        safety_url = os.getenv("CONTENT_SAFETY_URL")
        if not safety_url:
            raise RuntimeError("CONTENT_SAFETY_URL is required for CONTENT_SAFETY_PROVIDER=http")
        app.state.content_safety_provider = HttpContentSafetyProvider(
            safety_url,
            os.getenv("CONTENT_SAFETY_TOKEN", ""),
        )
    else:
        raise RuntimeError(f"Unsupported CONTENT_SAFETY_PROVIDER: {safety_provider_name}")
    try:
        yield
    finally:
        retention_task.cancel()
        with suppress(asyncio.CancelledError):
            await retention_task


app = FastAPI(
    title="猫猫魔镜 API",
    version="0.2.0",
    description="中立的服装合身分析与反馈 API，不替用户作购买决定。",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(mirror_router)
live_mirror_directory = Path(
    os.getenv("LIVE_MIRROR_DIR", str(Path(__file__).resolve().parents[1] / "static/live-mirror"))
)
if live_mirror_directory.is_dir():
    app.mount(
        "/live-mirror",
        StaticFiles(directory=live_mirror_directory, html=True),
        name="live-mirror",
    )
app.state.live_mirror_ready = (live_mirror_directory / "index.html").is_file()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
