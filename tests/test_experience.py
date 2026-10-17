from datetime import date

from backend.services.experience import bio_from_readme, duration, refresh_readme, total

TODAY = date(2026, 10, 18)


def test_duration_matches_the_site():
    assert duration("2025-09-15", "Present", TODAY) == "1Y 1M"
    assert duration("2022-10-24", "2025-04-25", TODAY) == "2Y 6M"


def test_total_carries_only_full_units_like_the_site():
    jobs = [("2025-09-15", "Present"), ("2025-04-25", "2025-09-01"), ("2022-10-24", "2025-04-25")]
    assert total(jobs, TODAY) == "3Y 11M"
    assert total([("2020-01-31", "2020-03-01")], TODAY) == "0Y 1M"  # -1 day is not borrowed from the month


def test_refresh_leaves_unmarked_text_alone():
    readme = "I have 9Y 9M of experience <!-- a comment -->"
    assert refresh_readme(readme, TODAY) == readme
    assert bio_from_readme(readme, TODAY) is None


def test_bio_template_with_escaped_dashes():
    readme = '<!--github-bio:{"template": "A -\\u002d B, Y-M-D", "experience": [["2025-09-15", "Present"]]}-->'
    assert bio_from_readme(readme, TODAY) == "A -- B, 1Y 1M"
