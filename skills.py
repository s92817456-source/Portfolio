"""
skills.py  —  Dynamic skill extraction & gap analysis
Replaces static dict with multi-strategy extraction:
  1. Curated domain-specific skill taxonomy (expanded)
  2. Regex pattern matching for years/certifications
  3. Optional spaCy NER for unseen skill terms
"""

from __future__ import annotations
import re
from typing import TypedDict

# ── Expanded Skill Taxonomy ────────────────────────────────────────────────────
SKILL_DB: dict[str, list[str]] = {
    "Languages & Query": [
        "python", "r", "sql", "scala", "java", "c++", "c#", "julia", "matlab",
        "bash", "shell scripting", "go", "rust", "typescript", "javascript",
        "sas", "hive", "spark sql", "presto",
    ],
    "ML & Deep Learning": [
        "machine learning", "deep learning", "neural networks", "transformers",
        "bert", "gpt", "llm", "reinforcement learning", "federated learning",
        "transfer learning", "few-shot learning", "zero-shot", "fine-tuning",
        "scikit-learn", "tensorflow", "keras", "pytorch", "jax", "xgboost",
        "lightgbm", "catboost", "random forest", "gradient boosting",
        "cnn", "rnn", "lstm", "gru", "attention", "diffusion models",
        "stable diffusion", "generative ai", "rag", "langchain", "llama",
    ],
    "Data Engineering": [
        "pandas", "numpy", "spark", "pyspark", "kafka", "airflow", "dbt",
        "etl", "data pipeline", "data warehouse", "data lake", "delta lake",
        "databricks", "hadoop", "flink", "beam", "prefect", "dagster",
    ],
    "AI Agents & Systems": [
        "ai agents", "autonomous agents", "langchain", "langgraph", "autogpt",
        "tool use", "function calling", "multi-agent", "agentic ai",
        "retrieval augmented generation", "vector database", "embeddings",
        "chroma", "pinecone", "weaviate", "faiss", "qdrant",
    ],
    "Statistics & Analytics": [
        "statistics", "statistical modeling", "hypothesis testing", "a/b testing",
        "regression", "bayesian", "time series", "forecasting", "causal inference",
        "experimental design", "data analysis", "exploratory data analysis",
        "feature engineering", "feature selection",
    ],
    "NLP": [
        "nlp", "natural language processing", "spacy", "nltk", "hugging face",
        "transformers", "named entity recognition", "sentiment analysis",
        "text classification", "summarization", "translation", "tokenization",
        "word embeddings", "word2vec", "glove",
    ],
    "Cloud & MLOps": [
        "aws", "gcp", "azure", "sagemaker", "vertex ai", "azure ml",
        "mlflow", "kubeflow", "bentoml", "seldon", "docker", "kubernetes",
        "terraform", "ci/cd", "github actions", "model monitoring",
        "a/b testing", "shadow deployment", "blue-green deployment",
    ],
    "Databases": [
        "postgresql", "mysql", "mongodb", "redis", "cassandra", "elasticsearch",
        "bigquery", "redshift", "snowflake", "databricks", "sqlite",
    ],
    "Visualization & BI": [
        "power bi", "tableau", "looker", "matplotlib", "seaborn", "plotly",
        "d3.js", "streamlit", "gradio", "dash", "metabase", "grafana",
    ],
    "Soft Skills": [
        "communication", "leadership", "problem solving", "critical thinking",
        "collaboration", "project management", "agile", "scrum", "stakeholder management",
        "presentation", "documentation", "mentoring",
    ],
}

# Flatten for quick lookup
_ALL_SKILLS: list[str] = [s for skills in SKILL_DB.values() for s in skills]


# ── Certification / Credential Patterns ───────────────────────────────────────
_CERT_PATTERNS: list[str] = [
    r"aws certified", r"google professional", r"azure certified",
    r"pmp", r"deep learning\.ai", r"coursera", r"udacity", r"tensorflow developer",
    r"databricks certified", r"cfa", r"scrum master",
]

# ── Experience Year Extraction ─────────────────────────────────────────────────
_EXP_PATTERNS: list[str] = [
    r"(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:work\s+)?experience",
    r"experience\s*(?:of|:)\s*(\d+)\s*years?",
    r"(\d+)\s*years?\s+exp",
    r"(\d{4})\s*[–-]\s*(?:present|current|now)",  # date ranges
]


class SkillGapResult(TypedDict):
    found: list[str]
    missing: list[str]
    score: float  # 0-100


class FullAnalysis(TypedDict):
    categories: dict[str, SkillGapResult]
    experience_years: int
    certifications: list[str]
    extra_skills: list[str]  # skills in resume NOT in JD (hidden strengths)


def extract_experience(text: str) -> int:
    """Return max years of experience found in text."""
    years: list[int] = []
    for pattern in _EXP_PATTERNS:
        for match in re.finditer(pattern, text.lower()):
            val = int(match.group(1))
            # Treat 4-digit numbers as year; estimate tenure
            if 1990 <= val <= 2030:
                years.append(2025 - val)
            elif 0 < val <= 40:
                years.append(val)
    return max(years, default=0)


def extract_certifications(text: str) -> list[str]:
    """Identify certifications / credentials mentioned in text."""
    found: list[str] = []
    text_l = text.lower()
    for pat in _CERT_PATTERNS:
        if re.search(pat, text_l):
            found.append(pat.replace(r"\\.", ".").title())
    return found


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _skill_in_text(skill: str, text_norm: str) -> bool:
    """Check if a skill phrase appears as whole word(s) in text."""
    pattern = r"\b" + re.escape(skill) + r"\b"
    return bool(re.search(pattern, text_norm))


def get_categorized_analysis(resume_text: str, job_text: str) -> dict[str, SkillGapResult]:
    """
    For each category, return found / missing skills and a coverage score.
    Only evaluates skills that the JD actually mentions.
    """
    r_norm = _normalise(resume_text)
    j_norm = _normalise(job_text)

    analysis: dict[str, SkillGapResult] = {}
    for category, skills in SKILL_DB.items():
        jd_skills = [s for s in skills if _skill_in_text(s, j_norm)]
        if not jd_skills:
            continue  # Skip categories irrelevant to this JD

        found = [s for s in jd_skills if _skill_in_text(s, r_norm)]
        missing = [s for s in jd_skills if not _skill_in_text(s, r_norm)]
        total = len(jd_skills)
        score = round((len(found) / total) * 100, 1) if total else 100.0
        analysis[category] = SkillGapResult(found=found, missing=missing, score=score)

    return analysis


def missing_skills(resume_text: str, job_text: str) -> list[str]:
    """Flat list of all missing skills (for backward compatibility)."""
    analysis = get_categorized_analysis(resume_text, job_text)
    return [s for cat in analysis.values() for s in cat["missing"]]


def extra_skills(resume_text: str, job_text: str) -> list[str]:
    """Skills candidate has that aren't in the JD — hidden strengths."""
    r_norm = _normalise(resume_text)
    j_norm = _normalise(job_text)
    return [
        s for s in _ALL_SKILLS
        if _skill_in_text(s, r_norm) and not _skill_in_text(s, j_norm)
    ]


def get_full_analysis(resume_text: str, job_text: str) -> FullAnalysis:
    return FullAnalysis(
        categories=get_categorized_analysis(resume_text, job_text),
        experience_years=extract_experience(resume_text),
        certifications=extract_certifications(resume_text),
        extra_skills=extra_skills(resume_text, job_text),
    )
