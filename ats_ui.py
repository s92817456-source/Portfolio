"""ats_ui.py — drop-in Streamlit panel. Call render_ats_panel(r, key) inside a tab."""
from __future__ import annotations
import streamlit as st

from ats_engine import compute_ats
from llm import llm_available
from resume_builder import rewrite_resume, resume_to_text, build_resume_pdf, build_resume_docx


def _color(s: float) -> str:
    return "#276749" if s >= 80 else ("#c05621" if s >= 65 else "#c53030")


def render_ats_panel(r: dict, key: str) -> None:
    ats = r.get("ats")
    if not ats:
        st.info("ATS data not available.")
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(
            f"<div class='score-hero'><div class='score-num' style='color:{_color(ats['ats_score'])}'>"
            f"{ats['ats_score']:.0f}</div><div class='score-label'>ATS SCORE / 100 · {ats['verdict']}</div></div>",
            unsafe_allow_html=True)
        if ats["gap_to_target"] > 0:
            st.caption(f"🎯 Target {ats['target']}+ → {ats['gap_to_target']} points to go")
        else:
            st.caption("✅ Target reached")
        if ats.get("req_source") == "local":
            st.caption("⚠️ Keywords extracted locally (less accurate). Reason: " + str(ats.get("req_error") or "no API key"))
    with c2:
        for label, b in ats["breakdown"].items():
            st.progress(min(b["score"] / b["max"], 1.0), text=f"{label}: {b['score']:.0f}/{b['max']}")

    for w in ats.get("warnings", []):
        st.warning(w)

    st.markdown("**🔴 Must-have keywords missing from your resume**")
    st.markdown("".join(f"<span class='chip-missing'>{k}</span>" for k in ats["missing_must"]) or "None 🎉",
                unsafe_allow_html=True)
    if ats["missing_nice"]:
        st.markdown("**🟡 Nice-to-have missing**")
        st.markdown("".join(f"<span class='chip-extra'>{k}</span>" for k in ats["missing_nice"]), unsafe_allow_html=True)
    st.markdown("**🟢 Keywords matched**")
    st.markdown("".join(f"<span class='chip-found'>{k}</span>" for k in ats["keywords_found"]) or "None",
                unsafe_allow_html=True)

    st.markdown("**📈 Action plan (biggest score gains first)**")
    for a in ats["action_plan"]:
        st.markdown(f"- **+{a['points']}** pts — {a['action']}")

    st.markdown("---")
    st.markdown("**✨ AI-improved resume**")
    if not llm_available():
        st.info("Set ANTHROPIC_API_KEY (env var or .streamlit/secrets.toml) to enable resume rewriting.")
        return

    skey = f"improved_{key}"
    if st.button("Generate improved resume", key=f"gen_{key}"):
        with st.spinner("Claude is rewriting your resume (truthfully)…"):
            try:
                data = rewrite_resume(r["resume_text"], r["job_desc"], ats["missing_must"], ats["missing_nice"])
                new_ats = compute_ats(resume_to_text(data), r["job_desc"], None, ats["reqs"])
                st.session_state[skey] = (data, new_ats)
            except Exception as e:
                st.error(f"Rewrite failed: {e}" + ("  → API key invalid/placeholder. Use your real key from console.anthropic.com." if "401" in str(e) else ""))

    if skey in st.session_state:
        data, new_ats = st.session_state[skey]
        m1, m2 = st.columns(2)
        m1.metric("ATS score before", f"{ats['ats_score']:.0f}")
        m2.metric("ATS score after", f"{new_ats['ats_score']:.0f}", f"{new_ats['ats_score'] - ats['ats_score']:+.0f}")
        st.caption("After-score assumes ATS-safe single-column format (our export is). Fill [X%] placeholders before sending.")

        if data.get("keyword_plan"):
            st.markdown("**Where each keyword was added / should go**")
            st.dataframe(data["keyword_plan"], use_container_width=True)
        if data.get("gaps_not_in_resume"):
            st.warning("Not in your resume (add only if true, else learn/skip): " + ", ".join(data["gaps_not_in_resume"]))
        with st.expander("What changed"):
            for c in data.get("changes", []):
                st.markdown(f"- {c}")
        with st.expander("Preview"):
            st.text(resume_to_text(data))

        d1, d2 = st.columns(2)
        try:
            d1.download_button("⬇ Improved resume (PDF)", build_resume_pdf(data), "improved_resume.pdf",
                               "application/pdf", key=f"pdf_{key}")
        except Exception as e:
            d1.error(f"PDF error: {e}")
        try:
            d2.download_button("⬇ Improved resume (DOCX)", build_resume_docx(data), "improved_resume.docx",
                               "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               key=f"docx_{key}")
        except Exception as e:
            d2.caption(f"DOCX unavailable: {e} (pip install python-docx)")