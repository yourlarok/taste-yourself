from __future__ import annotations

import asyncio
import base64
import json
import sqlite3

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.routes import (
    get_content_safety_provider,
    get_current_user,
    get_image_storage,
    get_wardrobe_repository,
    require_safe_image,
)
from app.catalog import GARMENTS
from app.domain.mirror import (
    CatCard,
    FunFaceQuestion,
    FunFaceResult,
    MirrorBootstrap,
    MirrorConversation,
    MirrorMessageCreate,
    MirrorReply,
    WellbeingAssessmentCreate,
    WellbeingAssessmentResult,
    WellbeingQuestion,
)
from app.providers.content_safety import ContentSafetyProvider
from app.providers.llm import LLMProvider
from app.providers.speech import (
    DisabledSpeechRecognizer,
    QwenASRRecognizer,
    SpeechRecognitionError,
)
from app.repositories.mirror import MirrorRepository
from app.repositories.wardrobe import WardrobeRepository
from app.services.fun_face import QUESTIONS as FUN_FACE_QUESTIONS
from app.services.fun_face import build_fun_face_result
from app.services.image_storage import InvalidImage, LocalImageStorage
from app.services.mirror_agent import MirrorAgent
from app.services.wellbeing import QUESTIONS, assess_wellbeing

router = APIRouter(prefix="/api/v1/mirror", tags=["cat-mirror"])


def get_mirror_repository(request: Request) -> MirrorRepository:
    return request.app.state.mirror_repository


def get_mirror_agent(request: Request) -> MirrorAgent:
    return request.app.state.mirror_agent


def get_mirror_vision_provider(request: Request) -> LLMProvider:
    return request.app.state.mirror_vision_provider


def get_speech_recognizer(
    request: Request,
) -> QwenASRRecognizer | DisabledSpeechRecognizer:
    return request.app.state.speech_recognizer


@router.post("/transcriptions")
async def transcribe_mirror_audio(
    audio: UploadFile = File(),
    recognizer: QwenASRRecognizer | DisabledSpeechRecognizer = Depends(
        get_speech_recognizer
    ),
    current_user: str = Depends(get_current_user),
) -> dict[str, str]:
    del current_user
    raw = await audio.read(10 * 1024 * 1024 + 1)
    try:
        text = await asyncio.to_thread(recognizer.transcribe, raw, audio.content_type or "")
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SpeechRecognitionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="mirror_asr_unavailable") from error
    return {"text": text}


@router.get("/bootstrap", response_model=MirrorBootstrap)
def mirror_bootstrap(
    repository: MirrorRepository = Depends(get_mirror_repository),
    current_user: str = Depends(get_current_user),
) -> MirrorBootstrap:
    return MirrorBootstrap(
        greeting="镜面亮起来了。今天想看看穿搭、做张猫猫趣味卡，还是整理一下状态？",
        suggestions=[
            "我周末要去海边，穿什么好看？",
            "帮我从衣橱里找一件适合今天的衣服",
            "我想做今天的猫猫趣味测试",
            "最近有点累，陪我整理一下状态",
        ],
        face_test_available_today=repository.face_available_today(current_user),
    )


@router.post(
    "/conversations",
    response_model=MirrorConversation,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    repository: MirrorRepository = Depends(get_mirror_repository),
    current_user: str = Depends(get_current_user),
) -> MirrorConversation:
    return MirrorConversation.model_validate(repository.create_conversation(current_user))


@router.post("/conversations/{conversation_id}/messages", response_model=MirrorReply)
def send_message(
    conversation_id: str,
    payload: MirrorMessageCreate,
    repository: MirrorRepository = Depends(get_mirror_repository),
    agent: MirrorAgent = Depends(get_mirror_agent),
    wardrobe: WardrobeRepository = Depends(get_wardrobe_repository),
    current_user: str = Depends(get_current_user),
) -> MirrorReply:
    if not repository.owns_conversation(conversation_id, current_user):
        raise HTTPException(status_code=404, detail="mirror_conversation_not_found")
    repository.add_message(conversation_id, current_user, "user", payload.content)
    garments = [
        {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "source": "preset",
            "audience": item.audience,
            "body_types": ",".join(item.body_types),
            "occasions": ",".join(item.occasions),
            "tags": ",".join(item.tags),
            "material": item.material,
            "silhouette": item.silhouette,
        }
        for item in GARMENTS
    ]
    garments.extend(
        {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "source": "wardrobe",
            "audience": item.audience,
            "body_types": ",".join(item.body_types),
            "occasions": ",".join(item.occasions),
            "tags": ",".join(item.tags),
            "material": "",
            "silhouette": "",
        }
        for item in wardrobe.list_garments(current_user)
    )
    try:
        reply, action = agent.reply(repository.recent_messages(conversation_id), garments)
    except (httpx.HTTPError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail="mirror_agent_unavailable") from error
    saved = repository.add_message(
        conversation_id,
        current_user,
        "assistant",
        reply,
        action.type,
        action.model_dump(),
    )
    return MirrorReply(
        conversation_id=conversation_id,
        message_id=saved["id"],
        reply=reply,
        action=action,
        created_at=saved["created_at"],
    )


@router.get("/wellbeing/questions", response_model=list[WellbeingQuestion])
def wellbeing_questions() -> list[WellbeingQuestion]:
    return [WellbeingQuestion.model_validate(item) for item in QUESTIONS]


@router.get("/fun-face/questions", response_model=list[FunFaceQuestion])
def fun_face_questions() -> list[FunFaceQuestion]:
    return [FunFaceQuestion.model_validate(item) for item in FUN_FACE_QUESTIONS]


@router.post("/fun-face/assessments", response_model=FunFaceResult)
async def create_fun_face_assessment(
    answers_json: str = Form(),
    image: UploadFile = File(),
    repository: MirrorRepository = Depends(get_mirror_repository),
    vision: LLMProvider = Depends(get_mirror_vision_provider),
    storage: LocalImageStorage = Depends(get_image_storage),
    content_safety: ContentSafetyProvider = Depends(get_content_safety_provider),
    current_user: str = Depends(get_current_user),
) -> FunFaceResult:
    if not repository.face_available_today(current_user):
        raise HTTPException(status_code=429, detail="fun_face_daily_limit_reached")
    try:
        answers = json.loads(answers_json)
        if not isinstance(answers, list):
            raise ValueError("fun_face_answers_invalid")
        answers = [int(item) for item in answers]
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail="fun_face_answers_invalid") from error
    try:
        stored = await storage.save(image, f"mirror/fun-face/{current_user}")
    except InvalidImage as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        await asyncio.to_thread(
            require_safe_image,
            content_safety,
            storage,
            stored.relative_path,
            "fun_face",
        )
        image_bytes = (storage.root / stored.relative_path).read_bytes()
        encoded = base64.b64encode(image_bytes).decode("ascii")
        messages = [
            {
                "role": "system",
                "content": (
                    "分析照片中非敏感、可直接观察的画面特征。不得猜测人格、健康、情绪障碍、"
                    "种族、年龄、性别、命运或社会身份。只输出 JSON，字段 photo_quality、"
                    "expression_energy、lighting_softness、style_clarity、eye_contact 为 0-100，"
                    "observations 为最多三条中性画面描述。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请评估这张趣味镜卡照片的画面特征。"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                ],
            },
        ]
        vision_result = await asyncio.to_thread(vision.complete_json, messages)
        result = build_fun_face_result(current_user, answers, vision_result)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (httpx.HTTPError, RuntimeError, OSError) as error:
        raise HTTPException(status_code=503, detail="fun_face_analysis_unavailable") from error
    finally:
        storage.delete(stored.relative_path)
    try:
        assessment_id, created_at = repository.save_fun_face(current_user, result)
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=429, detail="fun_face_daily_limit_reached") from error
    collected = repository.collect_card(current_user, assessment_id, result["card"])
    return FunFaceResult(
        id=assessment_id,
        overall_score=result["overall_score"],
        dimensions=result["dimensions"],
        observations=result["observations"],
        explanation=result["explanation"],
        notice=result["notice"],
        card=CatCard.model_validate(collected),
        created_at=created_at,
    )


@router.post("/wellbeing/assessments", response_model=WellbeingAssessmentResult)
def create_wellbeing_assessment(
    payload: WellbeingAssessmentCreate,
    repository: MirrorRepository = Depends(get_mirror_repository),
    current_user: str = Depends(get_current_user),
) -> WellbeingAssessmentResult:
    result = assess_wellbeing(payload)
    assessment_id, created_at = repository.save_wellbeing(
        current_user,
        payload.answers,
        payload.contributors,
        result["score"],
        result["state"],
        result,
    )
    collected = repository.collect_card(
        current_user,
        assessment_id,
        result["card"],
    )
    return WellbeingAssessmentResult(
        id=assessment_id,
        score=result["score"],
        state=result["state"],
        state_label=result["state_label"],
        possible_factors=result["possible_factors"],
        next_steps=result["next_steps"],
        notice=result["notice"],
        card=CatCard.model_validate(collected),
        created_at=created_at,
    )


@router.get("/cards", response_model=list[CatCard])
def list_cards(
    repository: MirrorRepository = Depends(get_mirror_repository),
    current_user: str = Depends(get_current_user),
) -> list[CatCard]:
    return [CatCard.model_validate(item) for item in repository.list_cards(current_user)]
