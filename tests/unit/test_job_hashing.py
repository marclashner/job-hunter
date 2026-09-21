"""Job description hashing tests."""

from app.services.job_hashing import job_content_hash, normalize_job_description


def test_description_hash_is_stable_across_whitespace_and_case() -> None:
    left = "  Build APIs  in Python.\nOwn on-call.  "
    right = "build apis in python. own on-call."
    assert normalize_job_description(left) == normalize_job_description(right)
    assert job_content_hash(left) == job_content_hash(right)
    assert len(job_content_hash(left)) == 64


def test_different_descriptions_hash_differently() -> None:
    assert job_content_hash("backend python") != job_content_hash("frontend typescript")
