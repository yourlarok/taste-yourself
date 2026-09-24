from typing import Literal

from pydantic import BaseModel, Field


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


class DeleteMyDataRequest(BaseModel):
    confirmation: Literal["DELETE"]
