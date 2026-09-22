"""Unit tests for text/NLP utilities."""

from jobpilot.sources.base import extract_salary_range, html_to_text


def test_html_to_text_strips_tags_keeps_breaks():
    raw = "<p>Hola<br>mundo</p><div>A</div><h3>B</h3>"
    assert html_to_text(raw) == "Hola\nmundo\nA\nB"


def test_html_to_text_max_len():
    assert len(html_to_text("abcdefghij", max_len=5)) == 5


def test_salary_range_usd_k():
    lo, hi, cur = extract_salary_range("$120k - $160k")
    assert lo == 120000.0 and hi == 160000.0 and cur == "USD"


def test_salary_range_eur():
    lo, hi, cur = extract_salary_range("60000€ - 75000€")
    assert lo == 60000.0 and hi == 75000.0 and cur == "EUR"


def test_salary_range_none():
    assert extract_salary_range(None) == (None, None, "")


def test_salary_range_single_value():
    lo, hi, cur = extract_salary_range("28k usd")
    assert lo == 28000.0 and hi is None and cur == "USD"
