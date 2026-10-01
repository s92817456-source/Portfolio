import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ats_engine import compute_ats, has_term, stem_text

GOOD = """Jane Doe
jane@x.com +91 98765 43210 linkedin.com/in/jane
SUMMARY
Marketing analyst with 4 years experience in SEO and content strategy.
SKILLS
SEO, Google Analytics, content marketing, HubSpot
EXPERIENCE
Led SEO strategy and increased organic traffic by 120%. Managed campaigns, reduced CPA by 30%.
Launched 12 email campaigns, improved CTR by 18%. Built dashboards in Google Analytics.
EDUCATION
BBA Marketing
PROJECTS
Blog growth project: grew to 50k visitors.""" * 1

REQS = {"must_have": ["seo", "google analytics", "hubspot", "salesforce"], "nice_to_have": ["content marketing"],
        "soft_skills": [], "source": "test"}


def test_stemming_and_alias():
    assert has_term("campaign", stem_text("ran campaigns"))
    assert has_term("machine learning", stem_text("built ML models"))


def test_missing_keyword_reported():
    r = compute_ats(GOOD, "jd", None, REQS)
    assert "salesforce" in r["missing_must"]
    assert "seo" not in r["missing_must"]


def test_score_bounds_and_plan():
    r = compute_ats(GOOD, "jd", None, REQS)
    assert 0 <= r["ats_score"] <= 100
    assert r["action_plan"][0]["points"] >= r["action_plan"][-1]["points"]


def test_empty_resume_is_low():
    assert compute_ats("hello", "jd", None, REQS)["ats_score"] < 40
