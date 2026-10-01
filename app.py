"""app.py - CORE-AI Resume Intelligence (Streamlit UI) with ATS score + improved resume."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pdf_reader import extract_text
from similarity import get_match_score, get_section_scores, get_engine_name
from skills import get_categorized_analysis, missing_skills, extra_skills, get_full_analysis
from resume_improver import improvement_suggestions
from pdf_report import generate_pdf_report_bytes
from ats_engine import compute_ats, extract_requirements, chunked_match
from ats_ui import render_ats_panel
from export_engine import generate_csv_export, generate_excel_export

st.set_page_config(
    page_title="CORE-AI | Resume Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "results" not in st.session_state:
    st.session_state.results = []
if "ranked" not in st.session_state:
    st.session_state.ranked = False

# ── NEW HIGH-CONTRAST CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;700&display=swap');

/* ── Global reset ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── App background: clean white ── */
.stApp {
    background-color: #f0f4f8;
    color: #1a202c;
}

/* ── Main content area ── */
section[data-testid="stMain"] > div {
    background-color: #f0f4f8;
}

/* ── Header ── */
.hud-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 50%, #1e3a5f 100%);
    border-radius: 16px;
    text-align: center;
    padding: 2.5rem 2rem 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 20px rgba(30, 58, 95, 0.3);
}
.hud-header h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.4rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 4px;
    margin: 0 0 0.4rem 0;
    text-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.hud-header p {
    color: #a8d4f5;
    font-size: 0.9rem;
    letter-spacing: 1px;
    margin: 0;
    font-weight: 400;
}

/* ── Engine badge ── */
.engine-badge {
    text-align: center;
    background: #ffffff;
    border: 1px solid #bee3f8;
    border-radius: 20px;
    display: inline-block;
    padding: 4px 16px;
    font-size: 0.75rem;
    color: #2b6cb0;
    font-weight: 500;
    margin-bottom: 1rem;
}

/* ── Cards ── */
.hud-card {
    background: #ffffff;
    border: 1.5px solid #bee3f8;
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 12px rgba(43, 108, 176, 0.08);
    border-top: 4px solid #3182ce;
}
.hud-card h3 {
    font-family: 'Space Grotesk', sans-serif;
    color: #1e3a5f;
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 1rem;
}

/* ── Score display ── */
.score-hero {
    text-align: center;
    padding: 1.5rem;
    background: linear-gradient(135deg, #ebf8ff, #e6fffa);
    border: 2px solid #bee3f8;
    border-radius: 14px;
    margin-bottom: 0.8rem;
}
.score-num {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 3.5rem;
    font-weight: 700;
    line-height: 1;
    color: #2b6cb0;
}
.score-label {
    color: #4a5568;
    font-size: 0.72rem;
    letter-spacing: 2px;
    margin-top: 0.4rem;
    font-weight: 600;
    text-transform: uppercase;
}

/* ── Skill chips ── */
.chip-found {
    display: inline-block;
    background: #c6f6d5;
    color: #22543d;
    border: 1px solid #9ae6b4;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.76rem;
    margin: 3px;
    font-weight: 600;
}
.chip-missing {
    display: inline-block;
    background: #fed7d7;
    color: #742a2a;
    border: 1px solid #fc8181;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.76rem;
    margin: 3px;
    font-weight: 600;
}
.chip-extra {
    display: inline-block;
    background: #e9d8fd;
    color: #44337a;
    border: 1px solid #d6bcfa;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.76rem;
    margin: 3px;
    font-weight: 600;
}

/* ── Suggestion cards ── */
.sug-critical {
    border-left: 4px solid #e53e3e;
    padding: 0.8rem 1.1rem;
    margin: 0.6rem 0;
    background: #fff5f5;
    border-radius: 0 10px 10px 0;
    box-shadow: 0 1px 4px rgba(229,62,62,0.1);
}
.sug-high {
    border-left: 4px solid #dd6b20;
    padding: 0.8rem 1.1rem;
    margin: 0.6rem 0;
    background: #fffaf0;
    border-radius: 0 10px 10px 0;
    box-shadow: 0 1px 4px rgba(221,107,32,0.1);
}
.sug-medium {
    border-left: 4px solid #3182ce;
    padding: 0.8rem 1.1rem;
    margin: 0.6rem 0;
    background: #ebf8ff;
    border-radius: 0 10px 10px 0;
    box-shadow: 0 1px 4px rgba(49,130,206,0.1);
}
.sug-low {
    border-left: 4px solid #38a169;
    padding: 0.8rem 1.1rem;
    margin: 0.6rem 0;
    background: #f0fff4;
    border-radius: 0 10px 10px 0;
    box-shadow: 0 1px 4px rgba(56,161,105,0.1);
}
.sug-label {
    font-size: 0.72rem;
    letter-spacing: 1px;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.sug-msg {
    font-size: 0.88rem;
    color: #2d3748;
    margin: 0.2rem 0;
    line-height: 1.5;
    font-weight: 500;
}
.sug-action {
    font-size: 0.82rem;
    color: #4a5568;
    font-style: italic;
    margin-top: 0.2rem;
}

/* ── Divider ── */
hr {
    border-color: #bee3f8 !important;
    margin: 1.5rem 0 !important;
}

/* ── Streamlit button ── */
.stButton > button {
    background: linear-gradient(135deg, #2b6cb0, #3182ce);
    color: #ffffff !important;
    border: none !important;
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: 2px;
    font-size: 0.85rem;
    font-weight: 700;
    padding: 0.75rem 2rem;
    border-radius: 10px;
    transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(49, 130, 206, 0.35);
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1e3a5f, #2b6cb0);
    box-shadow: 0 6px 20px rgba(49, 130, 206, 0.45);
    transform: translateY(-1px);
}

/* ── Streamlit inputs ── */
.stTextArea textarea {
    background: #f7fafc !important;
    border: 1.5px solid #bee3f8 !important;
    border-radius: 10px !important;
    color: #1a202c !important;
    font-size: 0.9rem !important;
}
.stTextArea textarea:focus {
    border-color: #3182ce !important;
    box-shadow: 0 0 0 3px rgba(49,130,206,0.15) !important;
}
.stTextArea label {
    color: #2d3748 !important;
    font-weight: 600 !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #f7fafc !important;
    border: 2px dashed #90cdf4 !important;
    border-radius: 10px !important;
    padding: 0.5rem !important;
}
[data-testid="stFileUploader"] label {
    color: #2d3748 !important;
    font-weight: 600 !important;
}
[data-testid="stFileUploadDropzone"] p {
    color: #4a5568 !important;
}

/* ── Expander ── */
div[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1.5px solid #bee3f8 !important;
    border-radius: 12px !important;
    margin-bottom: 0.8rem !important;
    box-shadow: 0 2px 8px rgba(43, 108, 176, 0.06) !important;
}
div[data-testid="stExpander"] summary {
    color: #1e3a5f !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.8rem 1rem !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #ebf8ff !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: #2b6cb0 !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}
.stTabs [aria-selected="true"] {
    background: #ffffff !important;
    color: #1e3a5f !important;
    box-shadow: 0 1px 4px rgba(43,108,176,0.15) !important;
}

/* ── Caption / small text ── */
.stCaption, [data-testid="stCaptionContainer"] p {
    color: #4a5568 !important;
    font-size: 0.82rem !important;
}

/* ── Metrics ── */
[data-testid="stMetricValue"] {
    color: #1e3a5f !important;
    font-weight: 700 !important;
    font-size: 1.6rem !important;
}
[data-testid="stMetricLabel"] {
    color: #4a5568 !important;
    font-weight: 600 !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div {
    background: linear-gradient(90deg, #3182ce, #38a169) !important;
    border-radius: 4px !important;
}

/* ── Checkbox ── */
.stCheckbox label {
    color: #2d3748 !important;
    font-weight: 500 !important;
}

/* ── Ranking label ── */
.rank-section-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.72rem;
    color: #4a5568;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 0.8rem;
    padding: 0.4rem 0.8rem;
    background: #ebf8ff;
    border-radius: 6px;
    display: inline-block;
    border: 1px solid #bee3f8;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg, #276749, #38a169) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: 0 3px 10px rgba(56,161,105,0.3) !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: linear-gradient(135deg, #22543d, #276749) !important;
    transform: translateY(-1px) !important;
}

/* ── Error / warning ── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hud-header">
    <h1>CORE-AI // RESUME INTELLIGENCE</h1>
    <p>Semantic AI-powered resume screening &amp; candidate ranking platform</p>
</div>
""", unsafe_allow_html=True)

engine = get_engine_name()
st.markdown(
    f"<div style='text-align:center;margin-bottom:1.2rem'><span class='engine-badge'>⚙ Engine: {engine}</span></div>",
    unsafe_allow_html=True,
)

# ── Input Panel ───────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("<div class='hud-card'><h3>📂 Resume Upload</h3>", unsafe_allow_html=True)
    resume_files = st.file_uploader(
        "Upload one or more PDF resumes",
        type=["pdf"],
        accept_multiple_files=True,
        key="multi_resume",
        help="Multiple resumes will be ranked against the job description.",
    )
    if resume_files:
        st.caption(f"✅ {len(resume_files)} resume(s) loaded")
    st.markdown("</div>", unsafe_allow_html=True)

with col_right:
    st.markdown("<div class='hud-card'><h3>📋 Job Description</h3>", unsafe_allow_html=True)
    job_desc = st.text_area(
        "Paste the full job description",
        height=200,
        placeholder="Paste complete JD including responsibilities, required skills, qualifications…",
    )
    if job_desc:
        word_count = len(job_desc.split())
        st.caption(f"📝 {word_count} words · {len(job_desc)} chars")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Analysis Trigger ──────────────────────────────────────────────────────────
col_btn, col_opts = st.columns([2, 1])
with col_btn:
    analyze = st.button("🚀  RUN AI DIAGNOSTIC", key="analyze_btn", use_container_width=True)
with col_opts:
    show_extras = st.checkbox("Show hidden strengths", value=True)
    show_quality = st.checkbox("Show quality breakdown", value=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _score_color(score: float) -> str:
    if score >= 70:
        return "#276749"   # dark green — readable on white
    elif score >= 45:
        return "#c05621"   # dark amber
    return "#c53030"       # dark red


def draw_radar(analysis: dict) -> go.Figure:
    cats = list(analysis.keys())
    scores = [analysis[c].get("score", 0) for c in cats]
    fig = go.Figure(data=go.Scatterpolar(
        r=scores + [scores[0]],
        theta=cats + [cats[0]],
        fill="toself",
        fillcolor="rgba(49, 130, 206, 0.15)",
        line=dict(color="#2b6cb0", width=2.5),
        marker=dict(color="#2b6cb0", size=6),
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(235,248,255,0.8)",
            radialaxis=dict(range=[0, 100], gridcolor="#bee3f8", tickfont=dict(color="#4a5568", size=10)),
            angularaxis=dict(gridcolor="#bee3f8", tickfont=dict(color="#2d3748", size=11)),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=300,
        margin=dict(l=30, r=30, t=20, b=20),
    )
    return fig


def draw_section_bars(section_scores: dict) -> go.Figure:
    labels = [k.title() for k, v in section_scores.items() if k != "overall"]
    values = [v for k, v in section_scores.items() if k != "overall"]
    colors = [
        "#38a169" if v >= 70 else ("#dd6b20" if v >= 45 else "#e53e3e")
        for v in values
    ]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=[f"{v:.0f}%" for v in values],
        textposition="outside",
        textfont=dict(color="#2d3748", family="Inter", size=11, weight="bold"),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(235,248,255,0.5)",
        xaxis=dict(range=[0, 118], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(gridcolor="#bee3f8", tickfont=dict(color="#2d3748", size=11)),
        height=200,
        margin=dict(l=10, r=55, t=10, b=10),
    )
    return fig


def render_suggestions(suggestions: list):
    priority_map = {
        "critical": ("🔴", "sug-critical", "#c53030"),
        "high":     ("🟠", "sug-high",     "#c05621"),
        "medium":   ("🔵", "sug-medium",   "#2b6cb0"),
        "low":      ("🟢", "sug-low",      "#276749"),
    }
    for tip in suggestions:
        if isinstance(tip, dict):
            p = tip.get("priority", "medium")
            icon, cls, color = priority_map.get(p, ("⚪", "sug-medium", "#4a5568"))
            st.markdown(f"""
<div class="{cls}">
  <div class="sug-label" style="color:{color}">{icon} {p} · {tip.get('category','')}</div>
  <div class="sug-msg">{tip.get('message','')}</div>
  <div class="sug-action">→ {tip.get('action','')}</div>
</div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='sug-medium'><div class='sug-msg'>• {tip}</div></div>", unsafe_allow_html=True)


# ── Analysis Pipeline ─────────────────────────────────────────────────────────
if analyze:
    if not resume_files:
        st.error("⚠️ Upload at least one resume PDF.")
    elif not job_desc.strip():
        st.error("⚠️ Paste a job description.")
    else:
        st.session_state.results = []
        progress = st.progress(0, text="Initialising AI engine…")
        with st.spinner("Extracting JD requirements…"):
            reqs = extract_requirements(job_desc)   # once per JD

        for i, resume_file in enumerate(resume_files):
            progress.progress(
                (i + 0.5) / len(resume_files),
                text=f"Analysing {resume_file.name}…"
            )
            text = extract_text(resume_file)
            score = chunked_match(text, job_desc)
            section_scores = get_section_scores(text, job_desc)
            full = get_full_analysis(text, job_desc)
            missing = missing_skills(text, job_desc)
            extras = extra_skills(text, job_desc)
            ats = compute_ats(text, job_desc, resume_file, reqs)

            suggestions, quality = improvement_suggestions(
                missing_skill_list=missing,
                match_score=score,
                resume_text=text,
                experience_years=full["experience_years"],
                certifications=full["certifications"],
                extra_skills=extras,
            )

            st.session_state.results.append({
                "name": resume_file.name,
                "score": score,
                "section_scores": section_scores,
                "analysis": full["categories"],
                "missing": missing,
                "extra_skills": extras,
                "quality": quality,
                "suggestions": suggestions,
                "experience_years": full["experience_years"],
                "certifications": full["certifications"],
                "ats": ats,
                "resume_text": text,
                "job_desc": job_desc,
            })

        progress.progress(1.0, text="✅ Analysis complete.")
        st.session_state.ranked = True
        progress.empty()


# ── Results Display ───────────────────────────────────────────────────────────
if st.session_state.results:
    ranked = sorted(st.session_state.results, key=lambda r: r["score"], reverse=True)

    st.markdown("---")
    st.markdown("<div class='rank-section-label'>CANDIDATE RANKING // SORTED BY SEMANTIC MATCH SCORE</div>", unsafe_allow_html=True)

    # Comparison chart
    if len(ranked) > 1:
        names = [r["name"].replace(".pdf", "") for r in ranked]
        overall = [r["score"] for r in ranked]
        bar_colors = ["#38a169" if s >= 70 else ("#dd6b20" if s >= 45 else "#e53e3e") for s in overall]
        fig_compare = go.Figure(go.Bar(
            x=names, y=overall,
            marker_color=bar_colors,
            text=[f"{s}%" for s in overall],
            textposition="outside",
            textfont=dict(family="Inter", size=12, color="#2d3748"),
        ))
        fig_compare.update_layout(
            title=dict(text="Candidate Match Score Comparison", font=dict(color="#2d3748", size=14, family="Space Grotesk")),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(235,248,255,0.5)",
            yaxis=dict(range=[0, 118], gridcolor="#bee3f8", tickfont=dict(color="#4a5568")),
            xaxis=dict(tickfont=dict(color="#2d3748", size=12)),
            showlegend=False,
            height=280,
            margin=dict(l=20, r=20, t=50, b=30),
        )
        st.plotly_chart(fig_compare, use_container_width=True)

    # Individual panels
    for rank, r in enumerate(ranked, 1):
        score = r["score"]
        color = _score_color(score)
        rank_labels = {1: "🥇 TOP MATCH", 2: "🥈 RUNNER-UP", 3: "🥉 THIRD"}
        rank_text = rank_labels.get(rank, f"#{rank}")
        expander_label = (
            f"{rank_text}  ·  {r['name'].replace('.pdf','')}  ·  {score}% match  ·  Quality {r['quality']}/10  ·  ATS {r['ats']['ats_score']:.0f}"
        )

        with st.expander(expander_label, expanded=(rank == 1)):
            c1, c2, c3 = st.columns([1, 1.8, 1.8])

            with c1:
                st.markdown(f"""
<div class="score-hero">
  <div class="score-num" style="color:{color}">{score}%</div>
  <div class="score-label">MATCH SCORE</div>
</div>
<div class="score-hero" style="margin-top:0.5rem;background:linear-gradient(135deg,#faf5ff,#e9d8fd)">
  <div class="score-num" style="color:#553c9a;font-size:2.8rem">{r['quality']}/10</div>
  <div class="score-label">QUALITY SCORE</div>
</div>""", unsafe_allow_html=True)
                if r.get("experience_years"):
                    st.metric("Experience", f"{r['experience_years']}+ yrs")
                if r.get("certifications"):
                    st.caption("🎓 " + " · ".join(r["certifications"]))

            with c2:
                st.markdown("**Section Scores**")
                st.plotly_chart(draw_section_bars(r["section_scores"]), use_container_width=True)

            with c3:
                st.markdown("**Skill Coverage by Domain**")
                if r["analysis"]:
                    st.plotly_chart(draw_radar(r["analysis"]), use_container_width=True)

            st.markdown("---")

            tab1, tab2, tab3, tab4 = st.tabs(["🔍 Skill Analysis", "💡 AI Recommendations", "📊 Quality Breakdown", "🎯 ATS Score & Improved Resume"])

            with tab1:
                for category, data in r["analysis"].items():
                    cov = data.get("score", 0)
                    col_cat, col_bar = st.columns([1, 2])
                    with col_cat:
                        st.markdown(f"**{category}**")
                        cov_color = "#276749" if cov >= 70 else ("#c05621" if cov >= 45 else "#c53030")
                        st.markdown(f"<span style='color:{cov_color};font-weight:700;font-size:0.9rem'>{cov:.0f}% covered</span>", unsafe_allow_html=True)
                    with col_bar:
                        found_html = "".join(f"<span class='chip-found'>{s}</span>" for s in data["found"])
                        miss_html  = "".join(f"<span class='chip-missing'>{s}</span>" for s in data["missing"])
                        if found_html or miss_html:
                            st.markdown(found_html + miss_html, unsafe_allow_html=True)
                    st.markdown("")
                if show_extras and r.get("extra_skills"):
                    st.markdown("**🌟 Bonus Skills (beyond JD scope)**")
                    chips = "".join(f"<span class='chip-extra'>{s}</span>" for s in r["extra_skills"][:12])
                    st.markdown(chips, unsafe_allow_html=True)

            with tab2:
                render_suggestions(r["suggestions"])

            with tab3:
                if show_quality:
                    qcols = st.columns(3)
                    metrics = [
                        ("Overall Quality", f"{r['quality']}/10", None),
                        ("Match Score",     f"{r['score']}%",      None),
                        ("Experience",      f"{r.get('experience_years','?')} yrs", None),
                    ]
                    for idx, (label, value, delta) in enumerate(metrics):
                        qcols[idx].metric(label, value, delta)

            with tab4:
                render_ats_panel(r, rank)

            st.markdown("---")
            try:
                pdf_bytes = generate_pdf_report_bytes(r)
                filename  = r["name"].replace(".pdf", "") + "_CORE-AI-Report.pdf"
                st.download_button(
                    label="📄 Download Full PDF Report",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    key=f"dl_{rank}",
                )
            except Exception as e:
                st.warning(f"PDF generation error: {e}")

    # Leaderboard
    if len(ranked) > 1:
        st.markdown("---")
        st.markdown("<div class='rank-section-label'>LEADERBOARD SUMMARY</div>", unsafe_allow_html=True)
        hdr = st.columns([0.3, 2.5, 1, 1, 1, 1])
        for col, label in zip(hdr, ["#", "Candidate", "Match", "Quality", "Gaps", "ATS"]):
            col.markdown(f"<span style='font-size:0.75rem;font-weight:700;color:#4a5568;text-transform:uppercase;letter-spacing:1px'>{label}</span>", unsafe_allow_html=True)

        for rank, r in enumerate(ranked, 1):
            sc = r["score"]
            sc_color = _score_color(sc)
            row = st.columns([0.3, 2.5, 1, 1, 1, 1])
            row[0].markdown(f"**{rank}**")
            row[1].markdown(f"**{r['name'].replace('.pdf','')}**")
            row[2].markdown(f"<span style='color:{sc_color};font-weight:700'>{sc}%</span>", unsafe_allow_html=True)
            row[3].markdown(f"{r['quality']}/10")
            row[4].markdown(f"<span style='color:#c53030;font-weight:600'>{len(r['missing'])} skills</span>", unsafe_allow_html=True)
            a = r['ats']['ats_score']
            row[5].markdown(f"<span style='color:{_score_color(a)};font-weight:700'>{a:.0f}</span>", unsafe_allow_html=True)

    # Batch export
    st.markdown("---")
    st.markdown("<div class='rank-section-label'>BATCH EXPORT</div>", unsafe_allow_html=True)
    e1, e2 = st.columns(2)
    try:
        e1.download_button("⬇ CSV (all candidates)", generate_csv_export(ranked), "core_ai_candidates.csv", "text/csv", key="exp_csv")
        e2.download_button("⬇ Excel tracker", generate_excel_export(ranked), "core_ai_candidates.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="exp_xlsx")
    except Exception as e:
        st.warning(f"Export error: {e}  (pip install openpyxl)")