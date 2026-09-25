from __future__ import annotations

from typing import Literal

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.catalog import (
    GARMENTS,
    demo_fit_request,
    fit_request_for_measurements,
    get_catalog_garment_path,
    get_garment,
)
from app.domain.auth import AuthResponse, DeleteMyDataRequest, WechatLoginRequest
from app.domain.capabilities import CapabilityItem, CapabilitySnapshot
from app.domain.experience import (
    BodyScanCreate,
    BodyScanFrame,
    BodyScanResult,
    CatalogGarment,
    ExperienceSession,
    ExperienceSessionCreate,
    GarmentSelection,
    RealtimeSessionResult,
    RecentExperience,
    StaticTryOnCreate,
    StaticTryOnResult,
)
from app.domain.models import (
    BodyMeasurements,
    FitAnalysisRequest,
    FitAnalysisResponse,
    FitFeedback,
    FitPreference,
    GarmentCategory,
    ProductFitData,
    UserFitProfile,
)
from app.domain.wardrobe import GarmentRecord, GarmentSizeChartInput, PersonImageRecord
from app.providers.body_scan import BodyScanProvider
from app.providers.content_safety import ContentSafetyProvider
from app.providers.realtime import RealtimeProvider
from app.providers.tryon import TryOnProvider
from app.repositories.body_scans import BodyScanRepository
from app.repositories.experience import ExperienceRepository
from app.repositories.feedback import FeedbackRepository
from app.repositories.fit_profiles import FitProfileRepository
from app.repositories.quota import QuotaRepository
from app.repositories.wardrobe import WardrobeRepository
from app.services.auth import InvalidToken, TokenService, WechatAuthService, WechatLoginFailed
from app.services.fit_analyzer import FitAnalyzer
from app.services.image_storage import InvalidImage, LocalImageStorage
from app.services.media_signing import MediaUrlSigner
from app.services.privacy import PrivacyService

router = APIRouter(prefix="/api/v1")
analyzer = FitAnalyzer()


def _provider_capability(
    key: str,
    label: str,
    provider: str,
    ready_notice: str,
    demo_notice: str,
) -> CapabilityItem:
    if provider in {"disabled", "unavailable"}:
        return CapabilityItem(
            key=key,
            label=label,
            state="unavailable",
            provider=provider,
            notice="当前环境尚未配置这项能力。",
        )
    if provider.startswith("mock"):
        return CapabilityItem(
            key=key,
            label=label,
            state="demo",
            provider=provider,
            notice=demo_notice,
        )
    return CapabilityItem(
        key=key,
        label=label,
        state="configured",
        provider=provider,
        notice=ready_notice,
    )


def get_feedback_repository(request: Request) -> FeedbackRepository:
    return request.app.state.feedback_repository


def get_fit_profile_repository(request: Request) -> FitProfileRepository:
    return request.app.state.fit_profile_repository


def get_experience_repository(request: Request) -> ExperienceRepository:
    return request.app.state.experience_repository


def get_tryon_provider(request: Request) -> TryOnProvider:
    return request.app.state.tryon_provider


def get_body_scan_provider(request: Request) -> BodyScanProvider:
    return request.app.state.body_scan_provider


def get_realtime_provider(request: Request) -> RealtimeProvider:
    return request.app.state.realtime_provider


def get_body_scan_repository(request: Request) -> BodyScanRepository:
    return request.app.state.body_scan_repository


def get_wardrobe_repository(request: Request) -> WardrobeRepository:
    return request.app.state.wardrobe_repository


def get_image_storage(request: Request) -> LocalImageStorage:
    return request.app.state.image_storage


def get_media_signer(request: Request) -> MediaUrlSigner:
    return request.app.state.media_signer


def get_privacy_service(request: Request) -> PrivacyService:
    return request.app.state.privacy_service


def get_content_safety_provider(request: Request) -> ContentSafetyProvider:
    return request.app.state.content_safety_provider


def get_quota_repository(request: Request) -> QuotaRepository:
    return request.app.state.quota_repository


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str:
    if not authorization:
        if request.app.state.app_env == "development":
            return "dev-user"
        raise HTTPException(status_code=401, detail="authentication_required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid_authorization_header")
    token_service: TokenService = request.app.state.token_service
    try:
        user_id = token_service.verify(token)
    except InvalidToken as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    if request.app.state.app_env == "production" and not request.app.state.user_repository.exists(
        user_id
    ):
        raise HTTPException(status_code=401, detail="user_not_found")
    return user_id


def require_session_owner(session: ExperienceSession | None, user_id: str) -> ExperienceSession:
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="experience_session_not_found")
    return session


def require_safe_image(
    provider: ContentSafetyProvider,
    storage: LocalImageStorage,
    relative_path: str,
    scene: str,
) -> None:
    try:
        allowed = provider.is_allowed(storage.root / relative_path, scene)
    except (httpx.HTTPError, ValueError, OSError) as error:
        storage.delete(relative_path)
        raise HTTPException(status_code=503, detail="content_safety_unavailable") from error
    if not allowed:
        storage.delete(relative_path)
        raise HTTPException(status_code=422, detail="content_rejected")


@router.get("/capabilities", response_model=CapabilitySnapshot)
def get_capabilities(request: Request) -> CapabilitySnapshot:
    """Expose runtime readiness without leaking credentials or provider endpoints."""
    tryon = _provider_capability(
        "static_tryon",
        "试穿照",
        request.app.state.tryon_provider.name,
        "真实生成 Provider 已配置；健康状态与结果质量仍需真机样本验收。",
        "当前返回演示结果，未调用真实换装模型。",
    )
    measurement = _provider_capability(
        "body_measurement",
        "尺寸画像",
        request.app.state.body_scan_provider.name,
        "测量 Provider 已配置；精度与误差范围仍需软尺对照验收。",
        "当前使用固定测试画像，不依据照片推断真实尺寸。",
    )
    realtime = _provider_capability(
        "realtime_tryon",
        "动态试衣",
        request.app.state.realtime_provider.name,
        "实时中继 Provider 已配置；仍需微信类目权限与真机网络验收。",
        "当前只验证 15 秒交互与降级流程，不生成实时换装画面。",
    )
    sizing_state = "demo" if measurement.state == "demo" else "partial"
    sizing = CapabilityItem(
        key="size_analysis",
        label="尺码差异",
        state=sizing_state,
        provider="fit-engine-v1",
        notice=(
            "当前使用固定测试画像；用户衣橱支持录入逐 SKU 成衣尺寸表。"
            if sizing_state == "demo"
            else "人体尺寸 Provider 已配置；用户衣橱可录入逐 SKU 成衣尺寸，仍需精度验收。"
        ),
    )
    items = [
        CapabilityItem(
            key="wardrobe",
            label="我的衣橱",
            state="ready",
            provider="private-media-storage",
            notice="图片上传、私有保存、签名读取和账号删除链路已实现。",
        ),
        tryon,
        sizing,
        measurement,
        realtime,
    ]
    states = {item.state for item in items}
    mode = "demo" if "demo" in states else "live" if states == {"ready"} else "mixed"
    return CapabilitySnapshot(
        environment=request.app.state.app_env,
        mode=mode,
        items=items,
    )


@router.post("/auth/dev-login", response_model=AuthResponse)
def dev_login(request: Request) -> AuthResponse:
    if request.app.state.app_env != "development":
        raise HTTPException(status_code=404, detail="not_found")
    return request.app.state.token_service.issue("dev-user")


@router.post("/auth/wechat", response_model=AuthResponse)
def wechat_login(payload: WechatLoginRequest, request: Request) -> AuthResponse:
    service: WechatAuthService | None = request.app.state.wechat_auth_service
    if service is None:
        raise HTTPException(status_code=503, detail="wechat_auth_not_configured")
    try:
        return service.login(payload.code)
    except (WechatLoginFailed, httpx.HTTPError) as error:
        raise HTTPException(status_code=401, detail="wechat_login_failed") from error


@router.delete("/me/data")
def delete_my_data(
    payload: DeleteMyDataRequest,
    privacy: PrivacyService = Depends(get_privacy_service),
    current_user: str = Depends(get_current_user),
) -> dict[str, str | dict[str, int]]:
    return {"status": "deleted", "deleted": privacy.delete_user_data(current_user)}


@router.get("/me/recent-experience", response_model=RecentExperience)
def get_recent_experience(
    repository: ExperienceRepository = Depends(get_experience_repository),
    wardrobe: WardrobeRepository = Depends(get_wardrobe_repository),
    signer: MediaUrlSigner = Depends(get_media_signer),
    current_user: str = Depends(get_current_user),
) -> RecentExperience:
    recent = repository.latest_for_user(current_user)
    if recent is None:
        raise HTTPException(status_code=404, detail="recent_experience_not_found")
    session, result_path = recent
    catalog_garment = get_garment(session.garment_id)
    uploaded_garment = wardrobe.get_garment(session.garment_id)
    garment_name = (
        catalog_garment.name
        if catalog_garment
        else uploaded_garment.name if uploaded_garment else "已删除的衣服"
    )
    return RecentExperience(
        session_id=session.id,
        garment_id=session.garment_id,
        garment_name=garment_name,
        updated_at=session.updated_at,
        result_url=signer.sign(result_path) if result_path else None,
    )


@router.get("/me/usage")
def get_my_usage(
    request: Request,
    quotas: QuotaRepository = Depends(get_quota_repository),
    current_user: str = Depends(get_current_user),
) -> dict[str, dict[str, int]]:
    usage = quotas.get(current_user)
    return {
        "static": {
            "used": usage["static_count"],
            "limit": request.app.state.static_daily_limit,
        },
        "realtime": {
            "used": usage["realtime_count"],
            "limit": request.app.state.realtime_daily_limit,
        },
    }


def require_garment(
    garment_id: str,
    wardrobe: WardrobeRepository | None = None,
) -> None:
    if get_garment(garment_id) is None and (
        wardrobe is None or wardrobe.get_garment(garment_id) is None
    ):
        raise HTTPException(status_code=404, detail="garment_not_found")


@router.get("/catalog/garments", response_model=list[CatalogGarment])
def list_garments() -> list[CatalogGarment]:
    return GARMENTS


@router.get("/catalog/garments/{garment_id}/image", response_class=FileResponse)
def get_catalog_garment_image(garment_id: str):
    image_path = get_catalog_garment_path(garment_id)
    if image_path is None:
        raise HTTPException(status_code=404, detail="garment_image_not_found")
    return FileResponse(image_path, media_type="image/webp")


@router.post(
    "/experience-sessions",
    response_model=ExperienceSession,
    status_code=status.HTTP_201_CREATED,
)
def create_experience_session(
    payload: ExperienceSessionCreate,
    repository: ExperienceRepository = Depends(get_experience_repository),
    wardrobe: WardrobeRepository = Depends(get_wardrobe_repository),
    current_user: str = Depends(get_current_user),
) -> ExperienceSession:
    require_garment(payload.garment_id, wardrobe)
    return repository.create(current_user, payload.garment_id)


@router.get("/experience-sessions/{session_id}", response_model=ExperienceSession)
def get_experience_session(
    session_id: str,
    repository: ExperienceRepository = Depends(get_experience_repository),
    current_user: str = Depends(get_current_user),
) -> ExperienceSession:
    return require_session_owner(repository.get(session_id), current_user)


@router.put("/experience-sessions/{session_id}/garment", response_model=ExperienceSession)
def select_session_garment(
    session_id: str,
    payload: GarmentSelection,
    repository: ExperienceRepository = Depends(get_experience_repository),
    wardrobe: WardrobeRepository = Depends(get_wardrobe_repository),
    current_user: str = Depends(get_current_user),
) -> ExperienceSession:
    require_garment(payload.garment_id, wardrobe)
    require_session_owner(repository.get(session_id), current_user)
    session = repository.select_garment(session_id, payload.garment_id)
    assert session is not None
    return session


@router.post(
    "/experience-sessions/{session_id}/static-tryon",
    response_model=StaticTryOnResult,
)
def generate_static_tryon(
    session_id: str,
    request: Request,
    payload: StaticTryOnCreate | None = None,
    repository: ExperienceRepository = Depends(get_experience_repository),
    provider: TryOnProvider = Depends(get_tryon_provider),
    wardrobe: WardrobeRepository = Depends(get_wardrobe_repository),
    storage: LocalImageStorage = Depends(get_image_storage),
    current_user: str = Depends(get_current_user),
    signer: MediaUrlSigner = Depends(get_media_signer),
    content_safety: ContentSafetyProvider = Depends(get_content_safety_provider),
    quotas: QuotaRepository = Depends(get_quota_repository),
) -> StaticTryOnResult:
    session = require_session_owner(repository.get(session_id), current_user)

    person_path = None
    if payload and payload.person_image_id:
        person = wardrobe.get_person_image(payload.person_image_id)
        if person is None or person.user_id != session.user_id:
            raise HTTPException(status_code=404, detail="person_image_not_found")
        person_path = storage.root / person.image_path

    uploaded_garment = wardrobe.get_garment(session.garment_id)
    garment_path = (
        storage.root / uploaded_garment.image_path
        if uploaded_garment
        else get_catalog_garment_path(session.garment_id)
    )
    catalog_garment = get_garment(session.garment_id)
    category = uploaded_garment.category if uploaded_garment else "tops"
    if catalog_garment and catalog_garment.category in {"bottom", "dress"}:
        category = "bottoms" if catalog_garment.category == "bottom" else "one-pieces"

    if not quotas.consume(current_user, "static", request.app.state.static_daily_limit):
        raise HTTPException(status_code=429, detail="static_daily_limit_reached")
    try:
        result = provider.generate_static(
            session.id,
            session.garment_id,
            person_path=person_path,
            garment_path=garment_path,
            category=category,
        )
    except (httpx.HTTPError, InvalidImage, OSError, ValueError) as error:
        quotas.refund(current_user, "static")
        raise HTTPException(status_code=503, detail="static_tryon_unavailable") from error
    if result.status == "failed":
        quotas.refund(current_user, "static")
    if result.result_url and result.result_url.startswith("/api/v1/media/"):
        relative_path = result.result_url.removeprefix("/api/v1/media/")
        try:
            require_safe_image(content_safety, storage, relative_path, "generated_tryon")
        except HTTPException as error:
            quotas.refund(current_user, "static")
            return result.model_copy(
                update={
                    "status": "failed",
                    "result_url": None,
                    "notice": (
                        "生成结果未通过内容安全检查，未保存或展示。"
                        if error.status_code == 422
                        else "内容安全服务暂不可用，生成结果未展示。"
                    ),
                }
            )
        repository.add_result(session.id, relative_path)
        result = result.model_copy(update={"result_url": signer.sign(relative_path)})
    return result


@router.post(
    "/experience-sessions/{session_id}/realtime",
    response_model=RealtimeSessionResult,
)
def create_realtime_tryon(
    session_id: str,
    request: Request,
    repository: ExperienceRepository = Depends(get_experience_repository),
    provider: RealtimeProvider = Depends(get_realtime_provider),
    quotas: QuotaRepository = Depends(get_quota_repository),
    current_user: str = Depends(get_current_user),
) -> RealtimeSessionResult:
    session = require_session_owner(repository.get(session_id), current_user)
    if not quotas.consume(current_user, "realtime", request.app.state.realtime_daily_limit):
        raise HTTPException(status_code=429, detail="realtime_daily_limit_reached")
    try:
        result = provider.create(session.id, session.garment_id)
    except (httpx.HTTPError, OSError, ValueError) as error:
        quotas.refund(current_user, "realtime")
        raise HTTPException(status_code=503, detail="realtime_tryon_unavailable") from error
    if result.status != "ready":
        quotas.refund(current_user, "realtime")
    return result


@router.get("/catalog/garments/{garment_id}/fit-demo", response_model=FitAnalysisResponse)
def analyze_demo_garment(garment_id: str) -> FitAnalysisResponse:
    require_garment(garment_id)
    return analyzer.analyze(demo_fit_request(garment_id))


@router.get("/catalog/garments/{garment_id}/fit-analysis", response_model=FitAnalysisResponse)
@router.get("/garments/{garment_id}/fit-analysis", response_model=FitAnalysisResponse)
def analyze_garment_for_current_user(
    garment_id: str,
    profiles: FitProfileRepository = Depends(get_fit_profile_repository),
    wardrobe: WardrobeRepository = Depends(get_wardrobe_repository),
    current_user: str = Depends(get_current_user),
) -> FitAnalysisResponse:
    require_garment(garment_id, wardrobe)
    profile = profiles.get(current_user)
    if profile is None:
        raise HTTPException(status_code=409, detail="fit_profile_required")
    uploaded = wardrobe.get_garment(garment_id)
    if uploaded is not None:
        if uploaded.user_id != current_user:
            raise HTTPException(status_code=404, detail="garment_not_found")
        product = wardrobe.get_size_chart(garment_id, current_user)
        if product is None:
            raise HTTPException(status_code=404, detail="product_size_chart_not_found")
        request = FitAnalysisRequest(
            profile=UserFitProfile(
                user_id=current_user,
                preference=FitPreference.REGULAR,
                measurements=BodyMeasurements.model_validate(profile["measurements_cm"]),
            ),
            product=product,
        )
    else:
        request = fit_request_for_measurements(
            garment_id,
            current_user,
            profile["measurements_cm"],
        )
    return analyzer.analyze(request).model_copy(
        update={
            "profile_source": profile["provider"],
            "measurement_uncertainty_cm": profile["measurement_uncertainty_cm"],
            "profile_updated_at": profile["updated_at"],
        }
    )


@router.put(
    "/wardrobe/garments/{garment_id}/size-chart",
    response_model=ProductFitData,
)
def save_wardrobe_size_chart(
    garment_id: str,
    payload: GarmentSizeChartInput,
    repository: WardrobeRepository = Depends(get_wardrobe_repository),
    current_user: str = Depends(get_current_user),
) -> ProductFitData:
    garment = repository.get_garment(garment_id)
    if garment is None or garment.user_id != current_user:
        raise HTTPException(status_code=404, detail="garment_not_found")
    category = {
        "tops": GarmentCategory.TOP,
        "bottoms": GarmentCategory.BOTTOM,
        "one-pieces": GarmentCategory.DRESS,
    }[garment.category]
    product = ProductFitData(
        product_id=garment_id,
        brand=payload.brand,
        category=category,
        stretch_percent=payload.stretch_percent,
        variants=payload.variants,
    )
    return repository.save_size_chart(garment_id, current_user, product)


@router.get(
    "/wardrobe/garments/{garment_id}/size-chart",
    response_model=ProductFitData,
)
def get_wardrobe_size_chart(
    garment_id: str,
    repository: WardrobeRepository = Depends(get_wardrobe_repository),
    current_user: str = Depends(get_current_user),
) -> ProductFitData:
    garment = repository.get_garment(garment_id)
    if garment is None or garment.user_id != current_user:
        raise HTTPException(status_code=404, detail="garment_not_found")
    product = repository.get_size_chart(garment_id, current_user)
    if product is None:
        raise HTTPException(status_code=404, detail="product_size_chart_not_found")
    return product


@router.delete("/me/fit-profile")
def delete_fit_profile(
    profiles: FitProfileRepository = Depends(get_fit_profile_repository),
    current_user: str = Depends(get_current_user),
) -> dict[str, int | str]:
    return {"status": "deleted", "deleted": profiles.delete(current_user)}


@router.get("/me/fit-profile")
def get_fit_profile(
    profiles: FitProfileRepository = Depends(get_fit_profile_repository),
    current_user: str = Depends(get_current_user),
) -> dict:
    profile = profiles.get(current_user)
    if profile is None:
        raise HTTPException(status_code=404, detail="fit_profile_not_found")
    return profile


@router.post("/body-scans", response_model=BodyScanResult, status_code=status.HTTP_201_CREATED)
def create_body_scan(
    payload: BodyScanCreate,
    repository: ExperienceRepository = Depends(get_experience_repository),
    scans: BodyScanRepository = Depends(get_body_scan_repository),
    provider: BodyScanProvider = Depends(get_body_scan_provider),
    current_user: str = Depends(get_current_user),
) -> BodyScanResult:
    if not payload.consented:
        raise HTTPException(status_code=422, detail="explicit_consent_required")
    require_session_owner(repository.get(payload.experience_session_id), current_user)
    return scans.create(current_user, payload.experience_session_id, provider.name)


@router.post("/body-scans/{scan_id}/frames", response_model=BodyScanFrame)
async def upload_body_scan_frame(
    scan_id: str,
    angle: Literal["front", "side", "back"] = Form(),
    image: UploadFile = File(),
    scans: BodyScanRepository = Depends(get_body_scan_repository),
    storage: LocalImageStorage = Depends(get_image_storage),
    content_safety: ContentSafetyProvider = Depends(get_content_safety_provider),
    current_user: str = Depends(get_current_user),
) -> BodyScanFrame:
    if scans.get_owner(scan_id) != current_user:
        raise HTTPException(status_code=404, detail="body_scan_not_found")
    try:
        stored = await storage.save(image, f"scans/{scan_id}")
    except InvalidImage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if stored.height <= stored.width or stored.height < 480:
        storage.delete(stored.relative_path)
        raise HTTPException(status_code=422, detail="body_scan_frame_must_be_full_length_portrait")
    require_safe_image(content_safety, storage, stored.relative_path, "body_scan")
    scans.add_frame(scan_id, angle, stored.relative_path)
    return BodyScanFrame(angle=angle, image_path=stored.relative_path)


@router.post("/body-scans/{scan_id}/complete", response_model=BodyScanResult)
def complete_body_scan(
    scan_id: str,
    scans: BodyScanRepository = Depends(get_body_scan_repository),
    provider: BodyScanProvider = Depends(get_body_scan_provider),
    storage: LocalImageStorage = Depends(get_image_storage),
    profiles: FitProfileRepository = Depends(get_fit_profile_repository),
    current_user: str = Depends(get_current_user),
) -> BodyScanResult:
    if scans.get_owner(scan_id) != current_user:
        raise HTTPException(status_code=404, detail="body_scan_not_found")
    experience_session_id = scans.get_experience_session_id(scan_id)
    assert experience_session_id is not None
    scans.set_status(scan_id, "processing")
    try:
        result = provider.process(
            scan_id,
            experience_session_id,
            scans.frames(scan_id, storage.root),
        )
    except (httpx.HTTPError, OSError, ValueError) as error:
        scans.set_status(scan_id, "failed")
        for relative_path in scans.delete_frames(scan_id):
            storage.delete(relative_path)
        raise HTTPException(status_code=503, detail="body_measurement_unavailable") from error
    scans.set_status(scan_id, result.status)
    if result.status == "completed":
        profiles.save(
            current_user,
            scan_id,
            result.provider,
            result.measurements_cm,
            result.measurement_uncertainty_cm,
        )
        for relative_path in scans.delete_frames(scan_id):
            storage.delete(relative_path)
    return result


@router.post(
    "/wardrobe/garments",
    response_model=GarmentRecord,
    status_code=status.HTTP_201_CREATED,
)
async def upload_garment(
    user_id: str | None = Form(default=None),
    name: str = Form(min_length=1, max_length=128),
    category: Literal["tops", "bottoms", "one-pieces"] = Form(),
    image: UploadFile = File(),
    repository: WardrobeRepository = Depends(get_wardrobe_repository),
    storage: LocalImageStorage = Depends(get_image_storage),
    current_user: str = Depends(get_current_user),
    signer: MediaUrlSigner = Depends(get_media_signer),
    content_safety: ContentSafetyProvider = Depends(get_content_safety_provider),
) -> GarmentRecord:
    try:
        stored = await storage.save(image, "garments")
    except InvalidImage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    require_safe_image(content_safety, storage, stored.relative_path, "garment_upload")
    record = repository.add_garment(current_user, name, category, stored)
    return record.model_copy(update={"image_url": signer.sign(record.image_path)})


@router.get("/wardrobe/garments", response_model=list[GarmentRecord])
def list_wardrobe_garments(
    user_id: str | None = Query(default=None),
    repository: WardrobeRepository = Depends(get_wardrobe_repository),
    current_user: str = Depends(get_current_user),
    signer: MediaUrlSigner = Depends(get_media_signer),
) -> list[GarmentRecord]:
    return [
        record.model_copy(update={"image_url": signer.sign(record.image_path)})
        for record in repository.list_garments(current_user)
    ]


@router.post(
    "/person-images",
    response_model=PersonImageRecord,
    status_code=status.HTTP_201_CREATED,
)
async def upload_person_image(
    user_id: str | None = Form(default=None),
    image: UploadFile = File(),
    repository: WardrobeRepository = Depends(get_wardrobe_repository),
    storage: LocalImageStorage = Depends(get_image_storage),
    current_user: str = Depends(get_current_user),
    content_safety: ContentSafetyProvider = Depends(get_content_safety_provider),
) -> PersonImageRecord:
    try:
        stored = await storage.save(image, "people")
    except InvalidImage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    require_safe_image(content_safety, storage, stored.relative_path, "person_upload")
    return repository.add_person_image(current_user, stored)


@router.get("/media/{relative_path:path}", response_class=FileResponse)
def get_media(
    relative_path: str,
    request: Request,
    expires: int | None = Query(default=None),
    signature: str | None = Query(default=None),
    storage: LocalImageStorage = Depends(get_image_storage),
    signer: MediaUrlSigner = Depends(get_media_signer),
):
    if request.app.state.app_env != "development" and (
        expires is None or signature is None or not signer.verify(relative_path, expires, signature)
    ):
        raise HTTPException(status_code=403, detail="invalid_media_signature")
    target = (storage.root / relative_path).resolve()
    if storage.root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="media_not_found")
    return FileResponse(target)


@router.post("/fit/analyze", response_model=FitAnalysisResponse)
def analyze_fit(payload: FitAnalysisRequest) -> FitAnalysisResponse:
    return analyzer.analyze(payload)


@router.post("/fit-feedback", status_code=status.HTTP_201_CREATED)
def record_fit_feedback(
    payload: FitFeedback,
    repository: FeedbackRepository = Depends(get_feedback_repository),
    current_user: str = Depends(get_current_user),
) -> dict[str, int | str]:
    feedback_id = repository.add(payload.model_copy(update={"user_id": current_user}))
    return {"id": feedback_id, "status": "accepted"}
