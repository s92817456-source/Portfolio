"""
resume_improver.py  —  Intelligent suggestion engine
Generates recruiter-grade, contextual improvement suggestions.
Uses GPT-style templates with data-driven personalization.
"""

from __future__ import annotations
import re
from typing import TypedDict


# ── Quality Scoring ────────────────────────────────────────────────────────────
_SECTION_WEIGHTS: dict[str, int] = {
    "skills": 20,
    "experience": 25,
    "education": 15,
    "projects": 20,
    "summary": 10,
    "achievements": 10,
}

_ACTION_VERBS = [
    "developed", "implemented", "designed", "optimized", "led", "built",
    "deployed", "architected", "engineered", "automated", "reduced",
    "improved", "accelerated", "launched", "scaled", "collaborated",
    "mentored", "researched", "published", "presented",
]

_QUANTIFICATION_PATTERN = re.compile(
    r"\b(\d+[\.,]?\d*\s*(%|x|×|percent|times|million|billion|k\b|ms\b|hrs?))",
    re.IGNORECASE,
)

_FORMAT_SIGNALS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(\+?\d[\d\s\-().]{7,}\d)"),
    "linkedin": re.compile(r"linkedin\.com", re.IGNORECASE),
    "github": re.compile(r"github\.com", re.IGNORECASE),
    "url": re.compile(r"https?://", re.IGNORECASE),
}


class QualityBreakdown(TypedDict):
    total: float
    sections: float
    length: float
    format: float
    action_verbs: float
    quantification: float
    links: float


def resume_quality_score(resume_text: str) -> tuple[float, QualityBreakdown]:
    """
    Returns (score/10, breakdown) based on weighted evaluation of:
    - Section completeness
    - Word count / length
    - Formatting signals (email, phone, LinkedIn, GitHub)
    - Action verb usage
    - Quantified achievements
    - Presence of links/portfolio
    """
    text_l = resume_text.lower()
    breakdown = QualityBreakdown(
        total=0, sections=0, length=0, format=0,
        action_verbs=0, quantification=0, links=0,
    )

    # Sections (0–3 pts)
    found_sections = sum(1 for s in _SECTION_WEIGHTS if s in text_l)
    breakdown["sections"] = round(min(found_sections / len(_SECTION_WEIGHTS) * 3, 3), 1)

    # Length (0–2 pts)
    words = len(resume_text.split())
    if 300 <= words <= 900:
        breakdown["length"] = 2.0
    elif 900 < words <= 1500:
        breakdown["length"] = 1.5
    elif 150 <= words < 300:
        breakdown["length"] = 1.0
    else:
        breakdown["length"] = 0.5

    # Format signals (0–1.5 pts)
    fmt_score = sum(0.375 for sig in _FORMAT_SIGNALS.values() if sig.search(resume_text))
    breakdown["format"] = round(min(fmt_score, 1.5), 2)

    # Action verbs (0–1.5 pts)
    verb_count = sum(1 for v in _ACTION_VERBS if v in text_l)
    breakdown["action_verbs"] = round(min(verb_count / 5 * 1.5, 1.5), 2)

    # Quantification (0–1.5 pts)
    quant_count = len(_QUANTIFICATION_PATTERN.findall(resume_text))
    breakdown["quantification"] = round(min(quant_count / 4 * 1.5, 1.5), 2)

    # Links / portfolio (0–0.5 pts)
    if _FORMAT_SIGNALS["github"].search(resume_text) or _FORMAT_SIGNALS["url"].search(resume_text):
        breakdown["links"] = 0.5

    total = sum([
        breakdown["sections"], breakdown["length"], breakdown["format"],
        breakdown["action_verbs"], breakdown["quantification"], breakdown["links"],
    ])
    breakdown["total"] = round(min(total, 10), 1)
    return breakdown["total"], breakdown


# ── Suggestion Engine ──────────────────────────────────────────────────────────
class Suggestion(TypedDict):
    category: str          # e.g. "Skills Gap", "Resume Format"
    priority: str          # "critical" | "high" | "medium" | "low"
    message: str
    action: str            # Specific actionable step


def improvement_suggestions(
    missing_skill_list: list[str],
    match_score: float,
    resume_text: str,
    experience_years: int = 0,
    certifications: list[str] | None = None,
    extra_skills: list[str] | None = None,
) -> tuple[list[Suggestion], float]:
    """
    Returns (suggestions, quality_score) with recruiter-grade,
    prioritised, contextual improvement tips.
    """
    suggestions: list[Suggestion] = []
    text_l = resume_text.lower()
    quality_score, breakdown = resume_quality_score(resume_text)

    # ── 1. Skills Gap ─────────────────────────────────────────────────────────
    critical_missing = missing_skill_list[:5]
    if critical_missing:
        for skill in critical_missing:
            suggestions.append(Suggestion(
                category="Skills Gap",
                priority="critical",
                message=f"'{skill.title()}' is required by the JD but absent from your resume.",
                action=f"Add a bullet under Skills/Projects demonstrating hands-on use of {skill.title()}.",
            ))

    if len(missing_skill_list) > 5:
        rest = ", ".join(s.title() for s in missing_skill_list[5:10])
        suggestions.append(Suggestion(
            category="Skills Gap",
            priority="high",
            message=f"Additional JD-required skills missing: {rest}.",
            action="Integrate these into project descriptions or a supplemental skills section.",
        ))

    # ── 2. Match Score Advice ─────────────────────────────────────────────────
    if match_score < 40:
        suggestions.append(Suggestion(
            category="Alignment",
            priority="critical",
            message="Semantic alignment with the JD is very low — the resume reads as a different domain.",
            action="Rewrite the professional summary to mirror the JD's language, goals, and key terms.",
        ))
    elif match_score < 65:
        suggestions.append(Suggestion(
            category="Alignment",
            priority="high",
            message="Moderate alignment — the role fit is not immediately obvious to ATS or recruiters.",
            action="Add a 3–4 line tailored summary at the top that directly addresses the JD's requirements.",
        ))
    else:
        suggestions.append(Suggestion(
            category="Alignment",
            priority="low",
            message="Good semantic alignment. Focus on differentiating yourself with impact metrics.",
            action="Add 2–3 quantified outcomes per role (e.g., 'Reduced inference latency by 40%').",
        ))

    # ── 3. Quantified Achievements ────────────────────────────────────────────
    quant_count = len(_QUANTIFICATION_PATTERN.findall(resume_text))
    if quant_count == 0:
        suggestions.append(Suggestion(
            category="Impact",
            priority="critical",
            message="No quantified achievements detected. Numbers are the #1 differentiator for technical roles.",
            action="Add metrics to at least 3 bullets: model accuracy %, latency, data size, cost savings, team size.",
        ))
    elif quant_count < 4:
        suggestions.append(Suggestion(
            category="Impact",
            priority="high",
            message=f"Only {quant_count} quantified achievement(s) found. Top resumes have 6–10.",
            action="Expand metrics to each major project/role (throughput, dataset size, error rate reduction).",
        ))

    # ── 4. Action Verbs ────────────────────────────────────────────────────────
    verb_count = sum(1 for v in _ACTION_VERBS if v in text_l)
    if verb_count < 3:
        suggestions.append(Suggestion(
            category="Language",
            priority="high",
            message="Weak action verb usage — bullets sound passive or descriptive rather than achievement-focused.",
            action="Start each bullet with a power verb: Architected, Engineered, Optimised, Deployed, Reduced.",
        ))

    # ── 5. Missing Sections ───────────────────────────────────────────────────
    missing_secs = [s for s in ["skills", "experience", "education", "projects"] if s not in text_l]
    if missing_secs:
        suggestions.append(Suggestion(
            category="Structure",
            priority="high",
            message=f"Missing standard sections: {', '.join(s.title() for s in missing_secs)}.",
            action="Add these sections. ATS systems score resumes by section presence.",
        ))

    # ── 6. Format Signals ─────────────────────────────────────────────────────
    if not _FORMAT_SIGNALS["linkedin"].search(resume_text):
        suggestions.append(Suggestion(
            category="Profile",
            priority="medium",
            message="LinkedIn URL not found.",
            action="Add your LinkedIn profile URL to the header — recruiters verify profiles before interviews.",
        ))
    if not _FORMAT_SIGNALS["github"].search(resume_text):
        suggestions.append(Suggestion(
            category="Profile",
            priority="medium",
            message="GitHub URL not found.",
            action="Add your GitHub to demonstrate active coding practice and open-source contributions.",
        ))

    # ── 7. Extra Skills (hidden strengths) ────────────────────────────────────
    if extra_skills and len(extra_skills) >= 3:
        extras = ", ".join(s.title() for s in extra_skills[:5])
        suggestions.append(Suggestion(
            category="Differentiation",
            priority="low",
            message=f"You have skills beyond the JD scope: {extras}.",
            action="Highlight these in your summary as differentiators (e.g., full-stack ML capabilities).",
        ))

    # ── 8. Certifications ─────────────────────────────────────────────────────
    if not certifications:
        suggestions.append(Suggestion(
            category="Credentials",
            priority="low",
            message="No certifications detected.",
            action="Add relevant certifications (AWS ML Specialty, Google Cloud ML Engineer, Deep Learning Specialisation).",
        ))

    # ── 9. Experience ─────────────────────────────────────────────────────────
    if experience_years == 0:
        suggestions.append(Suggestion(
            category="Experience",
            priority="medium",
            message="Could not detect years of experience — ATS may under-rank the resume.",
            action="State total experience explicitly: 'X years of experience in machine learning / data science'.",
        ))

    return suggestions, quality_score
