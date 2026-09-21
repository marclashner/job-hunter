"""Compensation regex extraction."""

from app.sources.compensation import parse_compensation


def test_parses_us_pay_transparency_range() -> None:
    text = "Pay Transparency: The base pay for this role is: $198,720 - $260,820 per year."
    parsed = parse_compensation(text)
    assert parsed is not None
    assert parsed.salary_min == 198720
    assert parsed.salary_max == 260820
    assert parsed.salary_currency == "USD"
    assert parsed.needs_llm is False


def test_parses_k_suffix_range() -> None:
    parsed = parse_compensation("Salary $150k-$180k USD")
    assert parsed is not None
    assert parsed.salary_min == 150000
    assert parsed.salary_max == 180000


def test_prefers_us_band_when_multiple_ranges() -> None:
    text = (
        "UK: £80,000 - £100,000. "
        "The base salary range for standard cost of living areas is: $156,900 - $196,100. "
        "High cost of living: $180,000 - $220,000."
    )
    parsed = parse_compensation(text)
    assert parsed is not None
    assert parsed.salary_min == 156900
    assert parsed.salary_max == 196100


def test_mentions_salary_without_numbers_needs_llm() -> None:
    parsed = parse_compensation("Competitive salary with generous annual cash bonus")
    assert parsed is not None
    assert parsed.needs_llm is True
    assert parsed.salary_min is None
