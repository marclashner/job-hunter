"""Deterministic hard-filter cases. Missing job fields must not fail the listing."""

from app.models.enums import EmploymentType, RemotePolicy, RemotePreference, Seniority
from app.schemas.candidate import Compensation
from app.scoring.hard_filters import (
    HardFilterCandidate,
    HardFilterRule,
    JobFilterInput,
    evaluate_hard_filters,
)


def _candidate(**overrides: object) -> HardFilterCandidate:
    values: dict[str, object] = {
        "target_titles": [
            "Senior Software Engineer",
            "Senior Backend Engineer",
            "Senior Full-Stack Engineer",
            "Senior AI Engineer",
        ],
        "seniority": Seniority.SENIOR,
        "preferred_locations": ["Remote, US"],
        "remote_preference": RemotePreference.REMOTE,
        "employment_preferences": [EmploymentType.FULL_TIME, EmploymentType.CONTRACT],
        "minimum_compensation": Compensation(amount=180000, currency="USD", period="year"),
        "excluded_industries": ["crypto", "gambling"],
    }
    values.update(overrides)
    return HardFilterCandidate.model_validate(values)


def _job(**overrides: object) -> JobFilterInput:
    values: dict[str, object] = {
        "title": "Senior Backend Engineer",
        "description": "Build Python APIs for a healthcare AI product.",
        "company": "Helix Care",
        "department": "Engineering",
        "location": "Remote - United States",
        "remote_policy": RemotePolicy.REMOTE,
        "employment_type": EmploymentType.FULL_TIME,
        "seniority": Seniority.SENIOR,
        "salary_min": 190000,
        "salary_max": 230000,
        "salary_currency": "USD",
    }
    values.update(overrides)
    return JobFilterInput.model_validate(values)


def test_perfect_match_passes_with_no_missing_information() -> None:
    result = evaluate_hard_filters(_job(), _candidate())
    assert result.passed is True
    assert result.failed_rules == []
    assert result.warnings == []
    assert result.missing_information == []
    assert result.salary_unknown is False


def test_obvious_mismatch_fails_multiple_rules() -> None:
    result = evaluate_hard_filters(
        _job(
            title="Engineering Manager",
            description="Lead a crypto trading desk in our London office.",
            location="London, UK",
            remote_policy=RemotePolicy.ONSITE,
            employment_type=EmploymentType.PART_TIME,
            seniority=Seniority.JUNIOR,
            salary_min=80000,
            salary_max=110000,
        ),
        _candidate(),
    )
    assert result.passed is False
    assert HardFilterRule.UNACCEPTABLE_ONSITE_REQUIREMENT.value in result.failed_rules
    assert HardFilterRule.UNACCEPTABLE_LOCATION.value in result.failed_rules
    assert HardFilterRule.BELOW_MINIMUM_SENIORITY.value in result.failed_rules
    assert HardFilterRule.UNACCEPTABLE_EMPLOYMENT_TYPE.value in result.failed_rules
    assert HardFilterRule.BELOW_MINIMUM_COMPENSATION.value in result.failed_rules
    assert HardFilterRule.TARGET_ROLE_MISMATCH.value in result.failed_rules
    assert HardFilterRule.EXCLUDED_INDUSTRY.value in result.failed_rules
    assert result.salary_unknown is False


def test_unknown_salary_does_not_fail() -> None:
    result = evaluate_hard_filters(
        _job(salary_min=None, salary_max=None, salary_currency=None),
        _candidate(),
    )
    assert result.passed is True
    assert result.salary_unknown is True
    assert "job_salary" in result.missing_information
    assert HardFilterRule.BELOW_MINIMUM_COMPENSATION.value not in result.failed_rules


def test_salary_min_below_floor_without_max_warns_instead_of_failing() -> None:
    result = evaluate_hard_filters(
        _job(salary_min=120000, salary_max=None),
        _candidate(),
    )
    assert result.passed is True
    assert result.salary_unknown is False
    assert "salary_ceiling_unknown" in result.warnings
    assert HardFilterRule.BELOW_MINIMUM_COMPENSATION.value not in result.failed_rules


def test_salary_max_below_minimum_fails() -> None:
    result = evaluate_hard_filters(
        _job(salary_min=100000, salary_max=120000),
        _candidate(),
    )
    assert result.passed is False
    assert result.failed_rules == [HardFilterRule.BELOW_MINIMUM_COMPENSATION.value]


def test_unknown_remote_policy_does_not_fail_onsite_or_location() -> None:
    result = evaluate_hard_filters(
        _job(remote_policy=None, location="San Francisco, CA"),
        _candidate(),
    )
    assert result.passed is True
    assert "job_remote_policy" in result.missing_information
    assert HardFilterRule.UNACCEPTABLE_ONSITE_REQUIREMENT.value not in result.failed_rules
    assert HardFilterRule.UNACCEPTABLE_LOCATION.value not in result.failed_rules


def test_hybrid_fails_for_remote_only_candidate() -> None:
    result = evaluate_hard_filters(_job(remote_policy=RemotePolicy.HYBRID), _candidate())
    assert result.passed is False
    assert HardFilterRule.UNACCEPTABLE_ONSITE_REQUIREMENT.value in result.failed_rules


def test_contradictory_location_warns_and_still_uses_structured_policy() -> None:
    result = evaluate_hard_filters(
        _job(location="Remote - United States", remote_policy=RemotePolicy.ONSITE),
        _candidate(),
    )
    assert "contradictory_location_information" in result.warnings
    assert result.passed is False
    assert HardFilterRule.UNACCEPTABLE_ONSITE_REQUIREMENT.value in result.failed_rules


def test_contradictory_onsite_text_with_remote_policy_does_not_fail() -> None:
    result = evaluate_hard_filters(
        _job(location="Onsite San Francisco", remote_policy=RemotePolicy.REMOTE),
        _candidate(),
    )
    assert "contradictory_location_information" in result.warnings
    assert result.passed is True
    assert HardFilterRule.UNACCEPTABLE_ONSITE_REQUIREMENT.value not in result.failed_rules


def test_missing_fields_do_not_fail() -> None:
    result = evaluate_hard_filters(
        JobFilterInput(title="Senior Backend Engineer", description="Build APIs."),
        _candidate(),
    )
    assert result.passed is True
    assert result.salary_unknown is True
    assert "job_salary" in result.missing_information
    assert "job_remote_policy" in result.missing_information
    assert "job_seniority" in result.missing_information
    assert "job_employment_type" in result.missing_information
    assert result.failed_rules == []


def test_blank_location_with_onsite_policy_does_not_fail_location() -> None:
    result = evaluate_hard_filters(
        _job(location=None, remote_policy=RemotePolicy.ONSITE),
        _candidate(),
    )
    assert "job_location" in result.missing_information
    assert HardFilterRule.UNACCEPTABLE_LOCATION.value not in result.failed_rules
    assert HardFilterRule.UNACCEPTABLE_ONSITE_REQUIREMENT.value in result.failed_rules


def test_onsite_unlisted_city_fails_location() -> None:
    result = evaluate_hard_filters(
        _job(location="Berlin, Germany", remote_policy=RemotePolicy.ONSITE),
        _candidate(),
    )
    assert HardFilterRule.UNACCEPTABLE_LOCATION.value in result.failed_rules


def test_staff_role_meets_senior_minimum() -> None:
    result = evaluate_hard_filters(_job(seniority=Seniority.STAFF), _candidate())
    assert HardFilterRule.BELOW_MINIMUM_SENIORITY.value not in result.failed_rules
    assert result.passed is True


def test_specialized_backend_candidate_rejects_frontend_title() -> None:
    result = evaluate_hard_filters(
        _job(title="Senior Frontend Engineer"),
        _candidate(target_titles=["Senior Backend Engineer", "Senior AI Engineer"]),
    )
    assert result.failed_rules == [HardFilterRule.TARGET_ROLE_MISMATCH.value]


def test_generic_software_engineer_target_accepts_frontend_title() -> None:
    result = evaluate_hard_filters(_job(title="Senior Frontend Engineer"), _candidate())
    assert HardFilterRule.TARGET_ROLE_MISMATCH.value not in result.failed_rules
    assert result.passed is True


def test_unclassified_title_warns_and_passes() -> None:
    result = evaluate_hard_filters(_job(title="Mystery Role"), _candidate())
    assert result.passed is True
    assert "title_unclassified" in result.warnings
    assert "job_role_family" in result.missing_information


def test_currency_mismatch_warns_and_does_not_fail() -> None:
    result = evaluate_hard_filters(_job(salary_currency="EUR"), _candidate())
    assert result.passed is True
    assert "compensation_currency_mismatch" in result.warnings


def test_excluded_industry_not_configured_does_not_fail_crypto() -> None:
    result = evaluate_hard_filters(
        _job(description="Crypto wallet infrastructure in Python."),
        _candidate(excluded_industries=[]),
    )
    assert result.passed is True
    assert HardFilterRule.EXCLUDED_INDUSTRY.value not in result.failed_rules


def test_unknown_industry_does_not_fail_when_exclusions_exist() -> None:
    result = evaluate_hard_filters(
        _job(description="Build internal developer tools in Python."),
        _candidate(),
    )
    assert result.passed is True
    assert "job_industry" in result.missing_information


def test_unconfigured_candidate_constraints_pass_any_job() -> None:
    result = evaluate_hard_filters(
        _job(
            title="Barista",
            location="Mars",
            remote_policy=RemotePolicy.ONSITE,
            employment_type=EmploymentType.PART_TIME,
            seniority=Seniority.JUNIOR,
            salary_max=20000,
        ),
        HardFilterCandidate(),
    )
    assert result.passed is True
    assert result.failed_rules == []
    assert "candidate_target_titles" in result.missing_information
