from uuid import uuid4

import pytest

from app.api.routes import get_content_safety_provider, get_tryon_provider
from app.domain.experience import StaticTryOnResult
from app.main import app


class TestContentSafetyProvider:
    name = "test-content-safety"

    def is_allowed(self, image_path, scene: str) -> bool:
        return image_path.is_file()


class TestTryOnProvider:
    name = "test-tryon"

    def generate_static(
        self,
        experience_session_id,
        garment_id,
        person_path=None,
        garment_path=None,
        category="tops",
    ) -> StaticTryOnResult:
        return StaticTryOnResult(
            job_id=str(uuid4()),
            experience_session_id=experience_session_id,
            garment_id=garment_id,
            status="completed",
            provider=self.name,
            preview_token=f"test:{garment_id}",
            notice="Automated test provider.",
        )


@pytest.fixture(autouse=True)
def test_only_providers():
    app.dependency_overrides[get_content_safety_provider] = TestContentSafetyProvider
    app.dependency_overrides[get_tryon_provider] = TestTryOnProvider
    yield
    app.dependency_overrides.pop(get_content_safety_provider, None)
    app.dependency_overrides.pop(get_tryon_provider, None)
