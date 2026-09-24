from pathlib import Path

from app.repositories.fit_profiles import FitProfileRepository


def test_fit_profile_keeps_latest_measurements_and_provenance(tmp_path: Path):
    repository = FitProfileRepository(tmp_path / "profiles.db")
    repository.save(
        "user-1",
        "scan-1",
        "provider-a",
        {"chest_cm": 91.2},
        {"chest_cm": 1.4},
    )
    repository.save(
        "user-1",
        "scan-2",
        "provider-b",
        {"chest_cm": 92.3},
        {"chest_cm": 0.9},
    )

    profile = repository.get("user-1")
    assert profile is not None
    assert profile["source_scan_id"] == "scan-2"
    assert profile["measurements_cm"] == {"chest_cm": 92.3}
    assert profile["measurement_uncertainty_cm"] == {"chest_cm": 0.9}
