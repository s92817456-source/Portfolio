"""
similarity.py  —  Semantic matching engine
Replaces TF-IDF cosine similarity with Sentence Transformers for deep semantic understanding.
Falls back to TF-IDF if sentence-transformers is unavailable.
"""

from __future__ import annotations
import re
from typing import TypedDict

# ── Attempt to load sentence-transformers ──────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer, util
    import torch
    _MODEL: SentenceTransformer | None = None

    def _get_model() -> SentenceTransformer:
        global _MODEL
        if _MODEL is None:
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        return _MODEL

    def _semantic_similarity(text_a: str, text_b: str) -> float:
        model = _get_model()
        emb_a = model.encode(text_a, convert_to_tensor=True)
        emb_b = model.encode(text_b, convert_to_tensor=True)
        return float(util.cos_sim(emb_a, emb_b)[0][0])

    SEMANTIC_AVAILABLE = True

except ImportError:
    SEMANTIC_AVAILABLE = False
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

    def _semantic_similarity(text_a: str, text_b: str) -> float:  # type: ignore[misc]
        vec = TfidfVectorizer(stop_words="english")
        vecs = vec.fit_transform([text_a, text_b])
        return float(sk_cosine(vecs[0:1], vecs[1:2])[0][0])


# ── Section extraction helpers ─────────────────────────────────────────────────
_SECTION_PATTERNS: dict[str, list[str]] = {
    "skills": [
        r"(?i)(technical\s+)?skills?[\s\S]{0,2000}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
        r"(?i)competenc(y|ies)[\s\S]{0,1500}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
    ],
    "experience": [
        r"(?i)(work\s+)?experience[\s\S]{0,3000}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
        r"(?i)employment[\s\S]{0,3000}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
    ],
    "projects": [
        r"(?i)projects?[\s\S]{0,2000}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
        r"(?i)portfolio[\s\S]{0,2000}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
    ],
    "education": [
        r"(?i)education[\s\S]{0,1500}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
        r"(?i)academic[\s\S]{0,1500}?(?=\n[A-Z][A-Z\s]{3,}|\Z)",
    ],
}


def _extract_section(text: str, section: str) -> str:
    """Extract a section from resume text using pattern matching."""
    patterns = _SECTION_PATTERNS.get(section, [])
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return ""


class SectionScores(TypedDict):
    skills: float
    experience: float
    projects: float
    education: float
    overall: float


def get_match_score(resume_text: str, job_text: str) -> float:
    """Overall semantic match score (0–100)."""
    return round(_semantic_similarity(resume_text, job_text) * 100, 1)


def get_section_scores(resume_text: str, job_text: str) -> SectionScores:
    """
    Compute per-section semantic similarity scores.
    Falls back to full-text score if a section can't be extracted.
    """
    sections = ["skills", "experience", "projects", "education"]
    scores: dict[str, float] = {}

    for section in sections:
        resume_section = _extract_section(resume_text, section) or resume_text
        # Compare extracted resume section against full JD for best context
        raw = _semantic_similarity(resume_section, job_text)
        scores[section] = round(raw * 100, 1)

    # Weighted overall: skills 35%, experience 35%, projects 20%, education 10%
    overall = (
        scores["skills"] * 0.35
        + scores["experience"] * 0.35
        + scores["projects"] * 0.20
        + scores["education"] * 0.10
    )
    scores["overall"] = round(overall, 1)
    return SectionScores(**scores)  # type: ignore[misc]


def get_engine_name() -> str:
    return "Sentence Transformers (all-MiniLM-L6-v2)" if SEMANTIC_AVAILABLE else "TF-IDF (fallback)"
