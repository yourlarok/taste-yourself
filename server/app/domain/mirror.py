from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MirrorIntent = Literal[
    "chat",
    "open_tryon",
    "show_garments",
    "open_wardrobe",
    "start_fun_face",
    "start_wellbeing",
    "open_atlas",
]


class MirrorConversation(BaseModel):
    id: str
    created_at: datetime


class MirrorMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message_cannot_be_blank")
        return value


class MirrorAction(BaseModel):
    type: MirrorIntent = "chat"
    payload: dict[str, str | list[str] | bool] = Field(default_factory=dict)


class MirrorReply(BaseModel):
    conversation_id: str
    message_id: str
    reply: str
    action: MirrorAction
    created_at: datetime


class MirrorBootstrap(BaseModel):
    name: str = "猫猫魔镜"
    greeting: str
    suggestions: list[str]
    face_test_available_today: bool


class CatCard(BaseModel):
    id: str
    family: Literal["fun-face", "wellbeing", "discovery"]
    cat_type: str
    title: str
    subtitle: str
    body: str
    palette: Literal["sun", "mist", "moon", "moss", "night"]
    image_key: str
    collected_at: datetime


class WellbeingQuestion(BaseModel):
    id: str
    text: str


class WellbeingAssessmentCreate(BaseModel):
    answers: list[int] = Field(min_length=5, max_length=5)
    contributors: list[
        Literal["sleep", "workload", "relationships", "physical", "uncertainty", "none"]
    ] = Field(default_factory=list, max_length=3)
    immediate_danger: bool = False

    @field_validator("answers")
    @classmethod
    def valid_answers(cls, answers: list[int]) -> list[int]:
        if any(answer < 0 or answer > 5 for answer in answers):
            raise ValueError("wellbeing_answers_must_be_between_0_and_5")
        return answers


class WellbeingAssessmentResult(BaseModel):
    id: str
    score: int
    state: Literal["steady", "tired", "strained", "low", "urgent"]
    state_label: str
    possible_factors: list[str]
    next_steps: list[str]
    notice: str
    card: CatCard
    created_at: datetime


class FunFaceQuestion(BaseModel):
    id: str
    text: str
    left_label: str
    right_label: str


class FunFaceResult(BaseModel):
    id: str
    overall_score: int
    dimensions: dict[str, int]
    observations: list[str]
    explanation: str
    notice: str
    card: CatCard
    created_at: datetime
