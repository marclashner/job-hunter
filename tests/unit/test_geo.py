"""Eligible country parsing from job locations."""

from app.sources.geo import parse_eligible_countries, preferred_country_codes


def test_remote_uk_is_gb() -> None:
    assert parse_eligible_countries("Remote, United Kingdom") == ["GB"]


def test_gitlab_multi_region_includes_us() -> None:
    codes = parse_eligible_countries("Remote, Canada; Remote, United States")
    assert codes == ["CA", "US"]


def test_bare_remote_has_no_country() -> None:
    assert parse_eligible_countries("Remote") == []


def test_us_cities_and_states() -> None:
    assert parse_eligible_countries("San Francisco, CA; New York, NY") == ["US"]


def test_does_not_treat_or_as_oregon() -> None:
    codes = parse_eligible_countries(
        "San Francisco, CA, New York, NY, Portland, OR, or Remote within Canada or United States"
    )
    assert "US" in codes
    assert "CA" in codes


def test_preferred_remote_us() -> None:
    assert preferred_country_codes(["Remote, US"]) == {"US"}
