"""
ai_engine.py  —  Claude-powered analysis engine
Replaces rule-based resume_improver.py with actual LLM calls.
Provides: AI suggestions, narrative summary, job-fit verdict, ATS density.
"""

from __future__ import annotations
import json
import re
from typing import TypedDict

# ── Anthropic API call ─────────────────────────────────────────────────────────
def _call_claude(prompt: str, system: str, max_tokens: int = 1000) -> str:
    """Call the Anthropic API and return text response."""
    import urllib.request
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]


# ── TypedDicts ─────────────────────────────────────────────────────────────────
class AISuggestion(TypedDict):
    category: str
    priority: str      # critical | high | medium | low
    message: str
    action: str


class FitVerdict(TypedDict):
    tier: str          # "Strongly Recommended" | "Consider" | "Reject"
    tier_code: str     # "green" | "amber" | "red"
    reason: str
    strengths: list[str]
    concerns: list[str]


class AIAnalysisResult(TypedDict):
    suggestions: list[AISuggestion]
    narrative_summary: str
    fit_verdict: FitVerdict
    quality_score: float


# ── ATS Keyword Density (local, no API needed) ─────────────────────────────────
def compute_ats_density(resume_text: str, job_text: str) -> dict[str, dict]:
    """
    For each significant keyword in the JD, count how many times it
    appears in the resume. Returns sorted dict by JD frequency desc.
    """
    stop = {
        "the","a","an","and","or","in","on","to","of","for","with",
        "is","are","be","has","have","will","we","you","our","their",
        "this","that","as","at","by","from","not","but","if","it",
        "its","we're","we'll","they","them","can","may","must","should",
        "your","who","which","what","how","all","any","each","also",
        "more","than","into","about","other","been","being","do","does",
    }

    def tokenize(text: str) -> list[str]:
        return [
            w.lower().strip(".,;:()[]\"'")
            for w in re.split(r"\s+", text)
            if len(w) > 3 and w.lower() not in stop
        ]

    jd_tokens = tokenize(job_text)
    resume_tokens = tokenize(resume_text)

    # Count frequencies
    from collections import Counter
    jd_freq = Counter(jd_tokens)
    resume_freq = Counter(resume_tokens)

    # Keep only multi-char meaningful terms, top 30 from JD
    keywords = {}
    for term, jd_count in jd_freq.most_common(40):
        if len(term) < 4:
            continue
        res_count = resume_freq.get(term, 0)
        keywords[term] = {
            "jd_count": jd_count,
            "resume_count": res_count,
            "present": res_count > 0,
            "gap": max(0, jd_count - res_count),
        }

    # Sort: missing first, then by JD frequency
    return dict(sorted(
        keywords.items(),
        key=lambda x: (x[1]["present"], -x[1]["jd_count"])
    ))


# ── Main AI Analysis ───────────────────────────────────────────────────────────
SYSTEM_RECRUITER = """You are a senior technical recruiter and resume expert at a top-tier tech company.
You have 15 years of experience hiring data scientists, ML engineers, and AI researchers.
You give candid, specific, actionable feedback. You write like a human expert — not a template.
Always respond with valid JSON only. No markdown fences, no preamble."""


def get_ai_suggestions(
    resume_text: str,
    job_text: str,
    match_score: float,
    missing_skills: list[str],
) -> list[AISuggestion]:
    """
    Ask Claude to generate recruiter-grade improvement suggestions.
    Returns list of AISuggestion TypedDicts.
    """
    prompt = f"""Analyse this resume against the job description and provide improvement suggestions.

MATCH SCORE: {match_score}%
MISSING SKILLS DETECTED: {', '.join(missing_skills[:10]) if missing_skills else 'None identified'}

JOB DESCRIPTION:
{job_text[:2000]}

RESUME (truncated to 2000 chars):
{resume_text[:2000]}

Return a JSON array of 5-8 suggestions. Each suggestion must have:
- "category": one of [Skills Gap, Alignment, Impact, Language, Structure, Profile, Differentiation]
- "priority": one of [critical, high, medium, low]
- "message": specific observation about this candidate's resume (1-2 sentences, be direct)
- "action": concrete step they can take TODAY (1 sentence, start with a verb)

Be specific to THIS resume and THIS job — not generic advice. Reference actual content you see.
Return ONLY the JSON array, nothing else."""

    try:
        raw = _call_claude(prompt, SYSTEM_RECRUITER, max_tokens=1200)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(raw)
        return [AISuggestion(**s) for s in parsed]
    except Exception as e:
        # Fallback: return one error suggestion
        return [AISuggestion(
            category="System",
            priority="medium",
            message=f"AI analysis unavailable: {str(e)[:80]}",
            action="Check API connectivity and retry.",
        )]


def get_narrative_summary(
    resume_text: str,
    job_text: str,
    match_score: float,
    quality_score: float,
    experience_years: int,
) -> str:
    """
    Ask Claude to write a 3-paragraph recruiter narrative about this candidate.
    """
    prompt = f"""Write a recruiter evaluation summary for this candidate.

MATCH SCORE: {match_score}% | QUALITY: {quality_score}/10 | EXPERIENCE: {experience_years} years

JOB DESCRIPTION (first 1500 chars):
{job_text[:1500]}

RESUME (first 1500 chars):
{resume_text[:1500]}

Write exactly 3 short paragraphs:
1. Overall impression and fit for this specific role
2. Key strengths relative to the JD requirements
3. Main concerns or gaps a hiring manager should probe in interview

Be direct, specific, and professional. No bullet points. Plain paragraphs only.
Respond with the 3 paragraphs separated by newlines — nothing else."""

    try:
        return _call_claude(prompt, SYSTEM_RECRUITER, max_tokens=500)
    except Exception as e:
        return f"Narrative summary unavailable. {str(e)[:100]}"


def get_fit_verdict(
    resume_text: str,
    job_text: str,
    match_score: float,
    missing_skills: list[str],
    experience_years: int,
) -> FitVerdict:
    """
    Ask Claude for a definitive job-fit tier decision with reasoning.
    """
    prompt = f"""Make a hiring decision for this candidate.

SEMANTIC MATCH: {match_score}% | EXPERIENCE: {experience_years} years
MISSING SKILLS: {', '.join(missing_skills[:8]) if missing_skills else 'None'}

JOB DESCRIPTION:
{job_text[:1500]}

RESUME:
{resume_text[:1500]}

Return a single JSON object with exactly these fields:
{{
  "tier": "Strongly Recommended" | "Consider" | "Reject",
  "tier_code": "green" | "amber" | "red",
  "reason": "One direct sentence explaining the verdict",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "concerns": ["concern 1", "concern 2"]
}}

Be decisive. A "Consider" means the hiring manager should interview but probe the gaps.
Return ONLY the JSON object."""

    try:
        raw = _call_claude(prompt, SYSTEM_RECRUITER, max_tokens=400)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(raw)
        return FitVerdict(**parsed)
    except Exception:
        # Fallback based on score
        if match_score >= 70:
            tier, code = "Strongly Recommended", "green"
        elif match_score >= 45:
            tier, code = "Consider", "amber"
        else:
            tier, code = "Reject", "red"
        return FitVerdict(
            tier=tier, tier_code=code,
            reason=f"Based on {match_score}% semantic match score.",
            strengths=[], concerns=[],
        )


def run_full_ai_analysis(
    resume_text: str,
    job_text: str,
    match_score: float,
    quality_score: float,
    missing_skills: list[str],
    experience_years: int,
) -> AIAnalysisResult:
    """
    Run all three AI analyses. Called once per candidate during screening.
    """
    suggestions = get_ai_suggestions(resume_text, job_text, match_score, missing_skills)
    narrative = get_narrative_summary(resume_text, job_text, match_score, quality_score, experience_years)
    verdict = get_fit_verdict(resume_text, job_text, match_score, missing_skills, experience_years)

    return AIAnalysisResult(
        suggestions=suggestions,
        narrative_summary=narrative,
        fit_verdict=verdict,
        quality_score=quality_score,
    )
