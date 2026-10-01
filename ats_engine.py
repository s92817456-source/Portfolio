"""ats_engine.py — Jobscan/Teal-style ATS score (0-100) with an action plan to reach 80+.

Score = Keywords 50 + Format/parsing 20 + Sections 10 + Contact 5 + Content quality 10 + Length 5
NOTE: weights are heuristic estimates, not calibrated on real hiring data. See tests/ + README.
"""
from __future__ import annotations
import re
from collections import Counter

from llm import call_claude, parse_json
from resume_improver import _ACTION_VERBS, _QUANTIFICATION_PATTERN

TARGET = 80

ALIASES = {
    "ml": "machine learning", "nlp": "natural language processing", "js": "javascript",
    "ai": "artificial intelligence", "k8s": "kubernetes", "genai": "generative ai",
    "llms": "llm", "ci/cd": "cicd", "powerbi": "power bi", "gcp": "google cloud",
}
_STOP = set("""the and for with you our are will this that from have has your who all any each also more than
into about other been being their they them can may must should not but its job role team work working
experience years year ability strong skills required preferred responsibilities requirements candidate based opportunity company location remote duration months stipend certificate
internship intern performance letter recommendation enrolled graduate related field knowledge familiarity
proficiency tools libraries such like deliver effective across extract excellent abilities""".split())

SECTION_PATTERNS = {
    "summary": r"summary|objective|profile",
    "skills": r"skills|technologies|competenc",
    "experience": r"experience|employment|work history",
    "education": r"education|academic",
    "projects": r"projects",
}


# ── Matching helpers ───────────────────────────────────────────────────────────
def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+#./ ]", " ", t.lower())).strip()


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def stem_text(t: str) -> str:
    return " ".join(_stem(w) for w in _norm(t).split())


def has_term(term: str, resume_stem: str) -> bool:
    term = term.lower().strip()
    cands = {term, ALIASES.get(term, term)} | {a for a, b in ALIASES.items() if b == term}
    for c in cands:
        s = stem_text(c)
        if s and re.search(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", resume_stem):
            return True
    return False


# ── 1. Requirement extraction (works for ANY industry via LLM) ─────────────────
_SYS = "You extract hiring requirements from job descriptions in ANY industry. Reply with JSON only."


def extract_requirements(job_text: str) -> dict:
    prompt = f"""From this job description extract what an ATS would scan for.
Return JSON: {{"role_title": str,
 "must_have": [8-20 hard skills, tools, certifications, qualifications, domain keywords EXACTLY as the JD words them],
 "nice_to_have": [up to 10 preferred/bonus items],
 "soft_skills": [up to 6]}}
Use short phrases (1-3 words), lowercase, no duplicates.

JOB DESCRIPTION:
{job_text[:4000]}"""
    try:
        d = parse_json(call_claude(prompt, _SYS, max_tokens=700))
        out = {k: list(dict.fromkeys(x.lower().strip() for x in d.get(k, []) if x.strip()))
               for k in ("must_have", "nice_to_have", "soft_skills")}
        out["role_title"] = d.get("role_title", "")
        if out["must_have"]:
            out["source"] = "llm"
            return out
    except Exception as e:
        err = str(e)[:150]
    else:
        err = "LLM returned no keywords"
    out = _fallback_requirements(job_text)
    out["llm_error"] = err
    return out


_EXTRA_TERMS = [
    "excel", "advanced excel", "power query", "dax", "dashboards", "kpi", "reporting", "mis",
    "data visualization", "data cleaning", "data analysis", "eda", "exploratory data analysis",
    "predictive modeling", "statistics", "tableau", "power bi", "matplotlib", "seaborn",
    "communication", "teamwork", "problem solving", "analytical", "stakeholder management",
    "machine learning", "scikit-learn", "tensorflow", "pytorch", "python", "r", "sql", "git",
    "crm", "seo", "google analytics", "sap", "tally", "jira", "figma",
]


def _core_jd(t: str) -> str:
    """Keep only Responsibilities/Requirements; drop 'About company' and stipend/benefits noise."""
    m = re.search(r"(?im)^\s*(responsibilit|requirement|qualification|what you|key skills|skills)", t)
    core = t[m.start():] if m else t
    e = re.search(r"(?im)^\s*(stipend|benefits|perks|what we offer|why join|compensation)", core)
    return core[:e.start()] if e else core


def _fallback_requirements(job_text: str) -> dict:
    """No API key / API error: taxonomy + generic business terms found in the core JD."""
    from skills import _ALL_SKILLS
    core = _core_jd(job_text)
    jd = stem_text(core)
    vocab = list(dict.fromkeys(_ALL_SKILLS + _EXTRA_TERMS))
    tax = [s for s in vocab if has_term(s, jd)]
    toks = [w for w in _norm(core).split() if len(w) > 3 and w not in _STOP and "." not in w]
    freq = [w for w, c in Counter(toks).most_common(30) if c >= 3 and w not in tax][:6]
    return {"role_title": "", "must_have": (tax + freq)[:20], "nice_to_have": [],
            "soft_skills": [], "source": "local"}


# ── 2. Format / parse analysis (two-column, tables, images, fonts) ─────────────
def _is_two_column(words: list[dict], width: float) -> bool:
    lines: dict[int, list[dict]] = {}
    for w in words:
        lines.setdefault(round(w["top"] / 4), []).append(w)
    multi = split = 0
    for ws in lines.values():
        if len(ws) < 2:
            continue
        multi += 1
        ws.sort(key=lambda w: w["x0"])
        for a, b in zip(ws, ws[1:]):
            if b["x0"] - a["x1"] > 0.06 * width and 0.3 * width < a["x1"] < 0.7 * width:
                split += 1
                break
    return multi >= 10 and split / multi > 0.25


def analyze_pdf_format(pdf_file) -> dict:
    import pdfplumber
    info = {"pages": 0, "two_column": False, "tables": 0, "images": 0, "fonts": 0, "chars": 0}
    try:
        if hasattr(pdf_file, "seek"):
            pdf_file.seek(0)
        with pdfplumber.open(pdf_file) as pdf:
            fonts, col_pages = set(), 0
            info["pages"] = len(pdf.pages)
            for p in pdf.pages:
                info["tables"] += len(p.find_tables())
                info["images"] += len(p.images)
                info["chars"] += len(p.chars)
                fonts |= {c.get("fontname", "").split("+")[-1].split("-")[0] for c in p.chars}
                if _is_two_column(p.extract_words(), p.width):
                    col_pages += 1
            info["fonts"] = len(fonts)
            info["two_column"] = col_pages > 0
    except Exception as e:
        info["error"] = str(e)[:100]
    finally:
        if hasattr(pdf_file, "seek"):
            pdf_file.seek(0)
    return info


def _format_score(fmt: dict | None) -> tuple[float, list[tuple[float, str]]]:
    if not fmt or fmt.get("error"):
        return 20.0, []
    pen: list[tuple[float, str]] = []
    if fmt["chars"] < 300:
        pen.append((20, "Text not extractable (scanned/image PDF). ATS will read nothing - export a text PDF."))
    if fmt["two_column"]:
        pen.append((8, "Two-column layout detected: ATS may mix left/right text. Use a single column."))
    if fmt["tables"]:
        pen.append((5, "Tables detected: many ATS drop table content. Use plain bullet lists."))
    if fmt["images"]:
        pen.append((3, "Images/icons/photo detected: ATS ignores them; remove skill bars & logos."))
    if fmt["fonts"] > 4:
        pen.append((2, f"{fmt['fonts']} different fonts: stick to 1-2 standard fonts."))
    if fmt["pages"] > 2:
        pen.append((2, f"{fmt['pages']} pages: keep to 1-2 pages."))
    return max(0.0, 20.0 - sum(p for p, _ in pen)), pen


# ── 3. Scoring ─────────────────────────────────────────────────────────────────
def _sections_found(text: str) -> list[str]:
    found = []
    for name, pat in SECTION_PATTERNS.items():
        for line in text.splitlines():
            l = line.strip().lower()
            if 0 < len(l) < 40 and re.search(pat, l):
                found.append(name)
                break
    return found


def compute_ats(resume_text: str, job_text: str, pdf_file=None, reqs: dict | None = None) -> dict:
    reqs = reqs or extract_requirements(job_text)
    rs = stem_text(resume_text)
    must = reqs["must_have"]
    nice = reqs.get("nice_to_have", []) + reqs.get("soft_skills", [])

    found_m = [k for k in must if has_term(k, rs)]
    miss_m = [k for k in must if k not in found_m]
    found_n = [k for k in nice if has_term(k, rs)]
    miss_n = [k for k in nice if k not in found_n]
    tw = 2 * len(must) + len(nice) or 1
    kw = round(50 * (2 * len(found_m) + len(found_n)) / tw, 1)
    pts_must, pts_nice = 100 / tw, 50 / tw

    fmt = analyze_pdf_format(pdf_file) if pdf_file is not None else None
    fscore, fpen = _format_score(fmt)

    secs = _sections_found(resume_text)
    sec_score = round(10 * len(secs) / len(SECTION_PATTERNS), 1)

    email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", resume_text))
    phone = bool(re.search(r"\+?\d[\d\s\-().]{8,}\d", resume_text))
    linkedin = "linkedin.com" in resume_text.lower()
    contact = 2 * email + 2 * phone + 1 * linkedin

    tl = resume_text.lower()
    quant = len(_QUANTIFICATION_PATTERN.findall(resume_text))
    verbs = sum(1 for v in _ACTION_VERBS if v in tl)
    content = round(min(quant / 5, 1) * 5 + min(verbs / 6, 1) * 5, 1)

    words = len(resume_text.split())
    length = 5 if 350 <= words <= 900 else (3 if 200 <= words < 350 or 900 < words <= 1200 else 1)

    total = round(kw + fscore + sec_score + contact + content + length, 1)

    plan: list[tuple[float, str]] = []
    for k in miss_m[:8]:
        plan.append((round(pts_must, 1), f"Add must-have keyword '{k}' (only if you truly have it) in Skills + one experience bullet."))
    for k in miss_n[:3]:
        plan.append((round(pts_nice, 1), f"Add nice-to-have keyword '{k}'."))
    plan += [(float(p), m) for p, m in fpen]
    for s in SECTION_PATTERNS:
        if s not in secs:
            plan.append((2.0, f"Add a standard '{s.title()}' heading."))
    if not email: plan.append((2.0, "Add an email address."))
    if not phone: plan.append((2.0, "Add a phone number."))
    if not linkedin: plan.append((1.0, "Add LinkedIn URL."))
    if quant < 5: plan.append((round(5 - min(quant, 5), 1), f"Only {quant} quantified results found; add numbers (%, $, time saved) to 5+ bullets."))
    if verbs < 6: plan.append((round(5 - 5 * min(verbs, 6) / 6, 1), "Start bullets with strong action verbs."))
    plan.sort(key=lambda x: -x[0])

    verdict = "ATS-ready" if total >= TARGET else ("Needs work" if total >= 65 else "At risk")
    return {
        "ats_score": total,
        "verdict": verdict,
        "target": TARGET,
        "gap_to_target": round(max(0, TARGET - total), 1),
        "breakdown": {
            "Keyword match": {"score": kw, "max": 50},
            "Format & parsing": {"score": round(fscore, 1), "max": 20},
            "Sections": {"score": sec_score, "max": 10},
            "Contact info": {"score": float(contact), "max": 5},
            "Content quality": {"score": content, "max": 10},
            "Length": {"score": float(length), "max": 5},
        },
        "keywords_found": found_m + found_n,
        "missing_must": miss_m,
        "missing_nice": miss_n,
        "warnings": [m for _, m in fpen],
        "format_info": fmt,
        "action_plan": [{"points": p, "action": a} for p, a in plan[:10]],
        "req_source": reqs.get("source", "llm"),
        "req_error": reqs.get("llm_error"),
        "reqs": reqs,
    }


# ── 4. Chunk-wise semantic score (fixes MiniLM ~256-token truncation) ──────────
def chunked_match(resume_text: str, job_text: str, size: int = 180) -> float:
    from similarity import _semantic_similarity

    def chunks(t: str) -> list[str]:
        w = t.split()
        return [" ".join(w[i:i + size]) for i in range(0, len(w), size)][:8] or [t]

    rc, jc = chunks(resume_text), chunks(job_text)
    best = [max(_semantic_similarity(r, j) for r in rc) for j in jc]
    return round(sum(best) / len(best) * 100, 1)