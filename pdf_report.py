"""
pdf_report.py  —  Professional PDF report generator
Uses FPDF2 with structured layout, colour coding, and section hierarchy.
"""

from __future__ import annotations
import io
from datetime import datetime

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False


class ResumeReport(FPDF):
    """Custom FPDF subclass with branded header/footer."""

    BRAND_R, BRAND_G, BRAND_B = 0, 140, 200  # Brand blue
    ACCENT_R, ACCENT_G, ACCENT_B = 30, 30, 50  # Dark navy

    @staticmethod
    def _safe_text(value) -> str:
        """Make text safe for built-in PDF fonts and wrap long tokens."""
        text = "" if value is None else str(value)

        # Helvetica is not a Unicode font. Replace common symbols used by
        # the app with ASCII equivalents so PDF generation is reliable.
        replacements = {
            "✓": "[OK]",
            "✗": "[X]",
            "→": "->",
            "•": "-",
            "–": "-",
            "—": "-",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
            "…": "...",
            "₹": "Rs.",
        }
        for old_char, new_char in replacements.items():
            text = text.replace(old_char, new_char)

        # FPDF2 cannot wrap a token that has no whitespace (e.g. a long URL,
        # path, ID, or generated string). Insert zero-width spaces so it can
        # break safely instead of raising "Not enough horizontal space...".
        import re
        text = re.sub(r"(\S{45})(?=\S)", r"\1 ", text)
        text = text.encode("latin-1", "replace").decode("latin-1")
        return text

    def safe_multi_cell(self, text, h=6):
        """Render wrapped text using the full printable width safely."""
        self.set_x(self.l_margin)
        safe = self._safe_text(text)
        self.multi_cell(self.epw, h, safe)
        self.set_x(self.l_margin)

    def header(self):
        self.set_fill_color(self.ACCENT_R, self.ACCENT_G, self.ACCENT_B)
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(0, 180, 230)
        self.set_y(5)
        self.cell(
            self.epw, 8, "CORE-AI  //  RESUME INTELLIGENCE REPORT", align="C"
        )
        self.ln(14)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(
            self.epw, 10,
            f"Generated {datetime.now().strftime('%d %b %Y')}  |  Page {self.page_no()}",
            align="C"
        )

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(self.BRAND_R, self.BRAND_G, self.BRAND_B)
        self.set_fill_color(240, 248, 255)
        self.cell(
            self.epw, 8, self._safe_text(f"  {title.upper()}"),
            new_x="LMARGIN", new_y="NEXT", fill=True
        )
        self.ln(2)
        self.set_text_color(30, 30, 30)

    def kv_row(self, label: str, value: str, bold_value: bool = False):
        # multi_cell() ends at the right edge by default in FPDF2.  Resetting
        # to the left margin makes consecutive overview rows independent and
        # prevents a following multi_cell(width=0) from receiving no space.
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(55, 7, label + ":", new_x="RIGHT", new_y="TOP")
        self.set_font("Helvetica", "B" if bold_value else "", 10)
        self.set_text_color(20, 20, 20)
        self.multi_cell(self.epw - 55, 7, self._safe_text(value), new_x="LMARGIN", new_y="NEXT")

    def score_bar(self, label: str, score: float, max_score: float = 100):
        """Render a horizontal percentage bar."""
        # Keep every column within the printable page width.  The previous
        # fixed widths added up to 199 mm, but the A4 content area is only
        # 180 mm with the configured margins.  That left FPDF with virtually
        # no room for the score text and caused its "Not enough horizontal
        # space to render a single character" exception.
        label_w = 55
        score_w = 18
        gap_w = 4
        bar_w = self.epw - label_w - gap_w - score_w

        try:
            numeric_score = float(score)
        except (TypeError, ValueError):
            numeric_score = 0.0
        pct = max(0.0, min(numeric_score / max_score, 1.0))
        filled = bar_w * pct

        self.set_font("Helvetica", "", 9)
        self.set_text_color(60, 60, 60)
        self.cell(label_w, 6, self._safe_text(label), new_x="RIGHT", new_y="TOP")

        # Background bar
        self.set_fill_color(220, 220, 220)
        x, y = self.get_x(), self.get_y()
        self.rect(x, y + 1, bar_w, 4, "F")

        # Filled bar (colour by score)
        if pct >= 0.7:
            self.set_fill_color(34, 139, 34)
        elif pct >= 0.45:
            self.set_fill_color(255, 165, 0)
        else:
            self.set_fill_color(200, 50, 50)
        self.rect(x, y + 1, filled, 4, "F")

        self.set_x(x + bar_w + gap_w)
        self.set_font("Helvetica", "B", 9)
        self.cell(score_w, 6, f"{numeric_score:.0f}%", new_x="LMARGIN", new_y="NEXT")


def generate_pdf_report_bytes(result: dict) -> io.BytesIO:
    """
    Generate a professional PDF from an analysis result dict.
    Returns BytesIO ready for Streamlit download_button.
    """
    if not FPDF_AVAILABLE:
        raise ImportError("fpdf2 is required: pip install fpdf2")

    pdf = ResumeReport(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=15, top=20, right=15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── Candidate Header ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(20, 20, 40)
    name = result.get("name", "Candidate").replace(".pdf", "")
    pdf.cell(0, 10, ResumeReport._safe_text(name), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    # ── Summary KVs ──────────────────────────────────────────────────────────
    pdf.section_title("Candidate Overview")
    pdf.kv_row("Match Score", f"{result.get('score', 0)}%", bold_value=True)
    pdf.kv_row("Quality Score", f"{result.get('quality', 0)}/10", bold_value=True)
    exp = result.get("experience_years", 0)
    pdf.kv_row("Experience", f"{exp}+ years detected" if exp else "Not detected")
    certs = result.get("certifications", [])
    pdf.kv_row("Certifications", ", ".join(certs) if certs else "None detected")
    pdf.ln(4)

    # ── Section Scores ────────────────────────────────────────────────────────
    section_scores = result.get("section_scores", {})
    if section_scores:
        pdf.section_title("Section-wise Semantic Score")
        for section, score in section_scores.items():
            if section == "overall":
                continue
            pdf.score_bar(section.title(), score)
        pdf.ln(4)

    # ── Skill Analysis per Category ───────────────────────────────────────────
    analysis = result.get("analysis", {})
    if analysis:
        pdf.section_title("Skill Gap Analysis")
        for category, data in analysis.items():
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(30, 90, 160)
            coverage = data.get("score", 0)
            pdf.cell(0, 7, ResumeReport._safe_text(
                f"  {category}  ({coverage:.0f}% coverage)"
            ), new_x="LMARGIN", new_y="NEXT")

            found = data.get("found", [])
            missing = data.get("missing", [])

            if found:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(34, 139, 34)
                pdf.set_x(pdf.l_margin)
                pdf.safe_multi_cell(
                    "[OK] " + ",  ".join(s.title() for s in found), 5
                )

            if missing:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(180, 50, 50)
                pdf.set_x(pdf.l_margin)
                pdf.safe_multi_cell(
                    "[X] " + ",  ".join(s.title() for s in missing), 5
                )

            pdf.set_text_color(20, 20, 20)
            pdf.ln(2)

    # ── Extra Skills ──────────────────────────────────────────────────────────
    extras = result.get("extra_skills", [])
    if extras:
        pdf.section_title("Candidate Differentiators (Beyond JD Scope)")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(50, 120, 80)
        pdf.set_x(pdf.l_margin)
        pdf.safe_multi_cell("  " + ",  ".join(s.title() for s in extras[:10]), 7)
        pdf.set_text_color(20, 20, 20)
        pdf.ln(4)

    # ── AI Suggestions ────────────────────────────────────────────────────────
    suggestions = result.get("suggestions", [])
    if suggestions:
        pdf.section_title("AI Improvement Recommendations")
        priority_colors = {
            "critical": (180, 30, 30),
            "high": (200, 100, 0),
            "medium": (0, 100, 160),
            "low": (60, 140, 60),
        }
        for tip in suggestions:
            if isinstance(tip, dict):
                priority = tip.get("priority", "medium")
                r, g, b = priority_colors.get(priority, (80, 80, 80))
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(r, g, b)
                pdf.cell(
                    0, 6,
                    ResumeReport._safe_text(
                        f"  [{priority.upper()}]  {tip.get('category', '')}"
                    ),
                    new_x="LMARGIN", new_y="NEXT",
                )
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.set_x(pdf.l_margin)
                pdf.safe_multi_cell(f"  {tip.get('message', '')}", 6)
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.set_x(pdf.l_margin)
                pdf.safe_multi_cell(f"  -> {tip.get('action', '')}", 6)
                pdf.ln(2)
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.set_x(pdf.l_margin)
                pdf.safe_multi_cell(f"  - {tip}", 6)

    # ── ATS Score ─────────────────────────────────────────────────────────────
    ats = result.get("ats")
    if ats:
        pdf.section_title("ATS Compatibility Score")
        pdf.kv_row("ATS Score", f"{ats['ats_score']}/100 - {ats['verdict']} (target {ats['target']}+)", bold_value=True)
        for label, b in ats["breakdown"].items():
            pdf.score_bar(label, b["score"], b["max"])
        pdf.ln(2)
        if ats.get("missing_must"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(180, 50, 50)
            pdf.safe_multi_cell("Must-have keywords missing: " + ", ".join(ats["missing_must"]), 6)
        for w in ats.get("warnings", []):
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(200, 100, 0)
            pdf.safe_multi_cell("! " + w, 5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 90, 160)
        pdf.safe_multi_cell("Action plan (biggest gains first):", 6)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(40, 40, 40)
        for a in ats.get("action_plan", []):
            pdf.safe_multi_cell(f"  +{a['points']} pts: {a['action']}", 5)
        pdf.set_text_color(20, 20, 20)
        pdf.ln(4)

    raw_bytes = bytes(pdf.output())
    return io.BytesIO(raw_bytes)