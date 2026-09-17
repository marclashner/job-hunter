"""Load replaceable candidate seed files from disk."""

from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from app.schemas.candidate import SeedBundle, SeedCandidateEvidence, SeedCandidateProfile

DEFAULT_DATA_DIR = Path("data/candidate")


def load_seed_bundle(data_dir: Path | None = None) -> SeedBundle:
    directory = data_dir or DEFAULT_DATA_DIR
    profile_path = directory / "profile.json"
    evidence_path = directory / "evidence.json"
    profile = SeedCandidateProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
    evidence = TypeAdapter(list[SeedCandidateEvidence]).validate_json(
        evidence_path.read_text(encoding="utf-8")
    )
    return SeedBundle(profile=profile, evidence=evidence)
