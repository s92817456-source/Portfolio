# CORE-AI // Resume Intelligence Platform

> Production-grade AI resume screening, semantic matching & candidate ranking.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CORE-AI Platform v2.0                        │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│  pdf_reader  │  similarity  │   skills     │  resume_improver   │
│              │              │              │                    │
│ pdfplumber   │ Sentence     │ 450+ skill   │ Recruiter-grade    │
│ layout-aware │ Transformers │ taxonomy     │ suggestion engine  │
│ extraction   │ (MiniLM-L6)  │ 10 domains   │ priority-ranked    │
│ section-wise │ + section    │ dynamic      │ contextual tips    │
│ parsing      │ scoring      │ extraction   │ quality scoring    │
└──────────────┴──────────────┴──────────────┴────────────────────┘
          ↓                ↓               ↓              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        app.py (Streamlit UI)                    │
│                                                                 │
│  • Multi-resume upload → ranked leaderboard                     │
│  • Radar chart per candidate (domain coverage)                  │
│  • Section-wise semantic score bars                             │
│  • Colour-coded skill chips (found/missing/extra)               │
│  • Priority-ranked AI improvement suggestions                   │
│  • PDF report download per candidate                            │
└─────────────────────────────────────────────────────────────────┘
```

## What's New vs v1

| Feature | v1 (Old) | v2 (New) |
|---|---|---|
| Matching | TF-IDF cosine | Sentence Transformers (all-MiniLM-L6-v2) |
| Section scoring | ❌ | ✅ Skills / Experience / Projects / Education |
| Skill DB | 30 skills, 3 categories | 450+ skills, 10 domains |
| Suggestions | Rule-based strings | Priority-ranked structured tips with actions |
| Extra skills | ❌ | ✅ Hidden strength detection |
| Quality scoring | Sections only | 6-factor weighted scoring |
| Experience detection | Basic regex | Multi-pattern year extraction |
| Certifications | ❌ | ✅ Auto-detected from text |
| PDF Report | Basic | Professional with colour bars, priorities |
| Ranking | Sort by score | Leaderboard + comparison bar chart |
| Fallback | Crash if no sentence-transformers | Graceful TF-IDF fallback |

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

For GPU-accelerated semantic matching:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install sentence-transformers
```

## Module API

### similarity.py
```python
from similarity import get_match_score, get_section_scores, get_engine_name

score = get_match_score(resume_text, jd_text)          # float 0-100
sections = get_section_scores(resume_text, jd_text)    # SectionScores TypedDict
# → {"skills": 72.3, "experience": 68.1, "projects": 55.0, "education": 80.0, "overall": 68.9}
```

### skills.py
```python
from skills import get_full_analysis

result = get_full_analysis(resume_text, jd_text)
# → {
#     "categories": {"ML & Deep Learning": {"found": [...], "missing": [...], "score": 75.0}, ...},
#     "experience_years": 4,
#     "certifications": ["Aws Certified"],
#     "extra_skills": ["docker", "kubernetes", ...]
# }
```

### resume_improver.py
```python
from resume_improver import improvement_suggestions

suggestions, quality = improvement_suggestions(
    missing_skill_list=["pytorch", "mlflow"],
    match_score=62.4,
    resume_text=text,
    experience_years=3,
    certifications=[],
    extra_skills=["tableau"],
)
# suggestions → List[Suggestion] with .category, .priority, .message, .action
# quality → float 0-10
```

## Extending

**Add skills**: Edit `SKILL_DB` in `skills.py` — add new categories or extend existing lists.

**Swap embedding model**: Change `"all-MiniLM-L6-v2"` in `similarity.py` to any SentenceTransformers model (e.g. `"all-mpnet-base-v2"` for higher accuracy, `"paraphrase-multilingual-MiniLM-L12-v2"` for multilingual).

**Add spaCy NER**: Install `spacy` + `en_core_web_sm`, then call `nlp(resume_text).ents` in `skills.py` to surface unseen skill terms from the candidate's text.
