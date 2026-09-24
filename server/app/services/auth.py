from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import httpx

from app.domain.auth import AuthResponse
from app.repositories.users import UserRepository


class InvalidToken(ValueError):
    pass


class WechatLoginFailed(ValueError):
    pass


class TokenService:
    def __init__(self, secret: str, ttl_seconds: int = 7 * 24 * 60 * 60) -> None:
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)

    def issue(self, user_id: str) -> AuthResponse:
        payload = {
            "sub": user_id,
            "exp": int(time.time()) + self.ttl_seconds,
        }
        encoded = self._encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = self._encode(
            hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        return AuthResponse(
            access_token=f"{encoded}.{signature}",
            expires_in=self.ttl_seconds,
            user_id=user_id,
        )

    def verify(self, token: str) -> str:
        try:
            encoded, provided_signature = token.split(".", maxsplit=1)
            expected = self._encode(
                hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(provided_signature, expected):
                raise InvalidToken("invalid_signature")
            payload = json.loads(self._decode(encoded))
            if int(payload["exp"]) < int(time.time()):
                raise InvalidToken("token_expired")
            return str(payload["sub"])
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            if isinstance(error, InvalidToken):
                raise
            raise InvalidToken("invalid_token") from error


class WechatAuthService:
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        users: UserRepository,
        tokens: TokenService,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.users = users
        self.tokens = tokens

    def login(self, code: str) -> AuthResponse:
        response = httpx.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": self.app_id,
                "secret": self.app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        openid = data.get("openid")
        if not openid:
            raise WechatLoginFailed(str(data.get("errmsg", "wechat_login_failed")))
        user_id = self.users.get_or_create_by_openid(openid)
        return self.tokens.issue(user_id)
