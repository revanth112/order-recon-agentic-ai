"""
Generate a professional PowerPoint presentation for the
Order Reconciliation Agentic AI project.

Usage:
    python scripts/generate_ppt.py
    python scripts/generate_ppt.py --output /path/to/output.pptx
"""

import argparse
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
NAVY = RGBColor(0x0D, 0x1B, 0x2A)
ACCENT_BLUE = RGBColor(0x15, 0x65, 0xC0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GREY_BG = RGBColor(0xF5, 0xF7, 0xFA)
LIGHT_BLUE_ROW = RGBColor(0xE3, 0xF2, 0xFD)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
ORANGE = RGBColor(0xE6, 0x5C, 0x00)
RED = RGBColor(0xC6, 0x28, 0x28)
DARK_TEXT = RGBColor(0x1A, 0x23, 0x2E)

# Slide dimensions: 16:9 widescreen (13.33 × 7.5 inches)
SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)
TOP_BAR_H = Inches(0.15)

TITLE_FONT = "Calibri"
BODY_FONT = "Calibri"
CODE_FONT = "Courier New"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_bg(slide, colour: RGBColor) -> None:
    """Fill slide background with a solid colour."""
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = colour


def _add_top_bar(slide) -> None:
    """Add a thin accent-blue bar across the top of the slide."""
    bar = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(0), Inches(0),
        SLIDE_W, TOP_BAR_H,
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT_BLUE
    bar.line.fill.background()


def _add_slide_number(slide, number: int) -> None:
    """Add a small slide-number label in the bottom-right corner."""
    tb = slide.shapes.add_textbox(
        Inches(12.5), Inches(7.2), Inches(0.7), Inches(0.25)
    )
    tf = tb.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    run = p.add_run()
    run.text = str(number)
    run.font.size = Pt(9)
    run.font.color.rgb = ACCENT_BLUE


def _title_box(slide, text: str,
               top: float = 0.2, left: float = 0.4,
               width: float = 12.5, height: float = 0.65,
               font_size: int = 30, colour: RGBColor = NAVY) -> None:
    """Add a styled title textbox."""
    tb = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = tb.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.name = TITLE_FONT
    run.font.bold = True
    run.font.size = Pt(font_size)
    run.font.color.rgb = colour


def _body_textbox(slide, lines: list[str],
                  left: float, top: float,
                  width: float, height: float,
                  font_size: int = 17,
                  colour: RGBColor = DARK_TEXT,
                  bold_words: list[str] | None = None,
                  bullet: bool = True) -> None:
    """Add a bullet-list textbox."""
    tb = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(2)
        if bullet:
            p.level = 0
        run = p.add_run()
        run.text = line
        run.font.name = BODY_FONT
        run.font.size = Pt(font_size)
        run.font.color.rgb = colour


def _add_table(slide,
               headers: list[str],
               rows: list[list[str]],
               col_widths: list[float],
               left: float, top: float,
               row_height: float = 0.38,
               header_font_size: int = 14,
               body_font_size: int = 13,
               severity_col: int | None = None) -> None:
    """Render a styled table onto the slide."""
    n_cols = len(headers)
    n_rows = len(rows) + 1  # +1 for header

    tbl_width = sum(col_widths)
    tbl_height = row_height * n_rows

    table = slide.shapes.add_table(
        n_rows, n_cols,
        Inches(left), Inches(top),
        Inches(tbl_width), Inches(tbl_height),
    ).table

    # Column widths
    for ci, cw in enumerate(col_widths):
        table.columns[ci].width = Inches(cw)

    # Header row
    for ci, hdr in enumerate(headers):
        cell = table.cell(0, ci)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = hdr
        run.font.name = TITLE_FONT
        run.font.bold = True
        run.font.size = Pt(header_font_size)
        run.font.color.rgb = WHITE

    # Data rows
    for ri, row in enumerate(rows):
        bg = WHITE if ri % 2 == 0 else LIGHT_BLUE_ROW
        for ci, cell_text in enumerate(row):
            cell = table.cell(ri + 1, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = cell_text
            run.font.name = BODY_FONT
            run.font.size = Pt(body_font_size)
            run.font.color.rgb = DARK_TEXT

            # Colour-code severity column if requested
            if severity_col is not None and ci == severity_col:
                txt = cell_text.strip().upper()
                if txt == "CRITICAL":
                    run.font.color.rgb = RED
                    run.font.bold = True
                elif txt == "WARNING":
                    run.font.color.rgb = ORANGE
                    run.font.bold = True
                elif txt == "INFO":
                    run.font.color.rgb = GREEN
                    run.font.bold = True


def _new_slide(prs: Presentation) -> object:
    """Add a blank slide with white/light background and top bar."""
    blank_layout = prs.slide_layouts[6]  # Blank
    slide = prs.slides.add_slide(blank_layout)
    _set_bg(slide, LIGHT_GREY_BG)
    _add_top_bar(slide)
    return slide


# ---------------------------------------------------------------------------
# Individual slide builders
# ---------------------------------------------------------------------------

def slide_01_title(prs: Presentation) -> None:
    blank_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_layout)
    _set_bg(slide, NAVY)
    _add_top_bar(slide)
    _add_slide_number(slide, 1)

    # Main title
    tb = slide.shapes.add_textbox(Inches(1), Inches(1.8), Inches(11.33), Inches(1.2))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "Order Reconciliation Agentic AI"
    run.font.name = TITLE_FONT
    run.font.bold = True
    run.font.size = Pt(40)
    run.font.color.rgb = WHITE

    # Subtitle
    tb2 = slide.shapes.add_textbox(Inches(1), Inches(3.15), Inches(11.33), Inches(0.7))
    tf2 = tb2.text_frame
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.CENTER
    run2 = p2.add_run()
    run2.text = "Multi-Agent Order Reconciliation System"
    run2.font.name = TITLE_FONT
    run2.font.bold = False
    run2.font.size = Pt(24)
    run2.font.color.rgb = RGBColor(0xBB, 0xDE, 0xFB)

    # Tagline
    tb3 = slide.shapes.add_textbox(Inches(1), Inches(4.0), Inches(11.33), Inches(0.6))
    tf3 = tb3.text_frame
    p3 = tf3.paragraphs[0]
    p3.alignment = PP_ALIGN.CENTER
    run3 = p3.add_run()
    run3.text = "Powered by LangGraph · Azure OpenAI GPT-4o · FAISS RAG · SQLite · Streamlit"
    run3.font.name = BODY_FONT
    run3.font.size = Pt(16)
    run3.font.color.rgb = RGBColor(0x90, 0xCA, 0xF9)

    # Decorative divider line
    line = slide.shapes.add_shape(
        1, Inches(3.5), Inches(4.75), Inches(6.33), Inches(0.04)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = ACCENT_BLUE
    line.line.fill.background()


def slide_02_problem(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 2)
    _title_box(slide, "The Problem")

    bullets = [
        "• Finance & operations teams reconcile invoices, POs, and delivery records manually",
        "• The process is slow, error-prone, and causes delays in month-end closing",
        "• High volume of invoices leads to missed discrepancies",
        "• Manual checks are inconsistent across vendors and procurement teams",
        "• No real-time visibility into reconciliation status or exception trends",
    ]
    _body_textbox(slide, bullets, 0.5, 1.2, 12.33, 5.5, font_size=18)


def slide_03_solution(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 3)
    _title_box(slide, "The Solution — Agentic AI Pipeline")

    bullets = [
        "• Accepts invoice JSON as input",
        "• Extracts structured fields using Azure OpenAI GPT-4o + Pydantic validation",
        "• Matches invoices to POs using configurable tolerance rules per vendor",
        "• Identifies discrepancies: price, quantity, product codes, currency mismatches",
        "• Auto-approves, blocks, or flags invoices for human review",
        "• Persists all data to a SQLite order database",
        "• Generates exception reports via a Streamlit dashboard",
        "• Full observability: mismatch metrics, pipeline traces, confidence scoring",
    ]
    _body_textbox(slide, bullets, 0.5, 1.2, 12.33, 5.8, font_size=17)


def slide_04_tech_stack(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 4)
    _title_box(slide, "Technology Stack")

    headers = ["Layer", "Technology"]
    rows = [
        ["LLM", "Azure OpenAI GPT-4o (via Azure AI Foundry)"],
        ["Embeddings", "Azure OpenAI text-embedding-ada-002"],
        ["Agent Framework", "LangGraph (StateGraph)"],
        ["RAG", "LangChain + FAISS (local vector index)"],
        ["Database", "SQLite (built-in Python)"],
        ["UI", "Streamlit"],
        ["Validation", "Pydantic v2"],
        ["Data Processing", "Pandas, NumPy"],
        ["Visualisation", "Plotly"],
    ]
    _add_table(slide, headers, rows,
               col_widths=[3.2, 8.5],
               left=0.9, top=1.25,
               row_height=0.45,
               header_font_size=15,
               body_font_size=14)


def slide_05_architecture(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 5)
    _title_box(slide, "System Architecture")

    flow_steps = [
        ("Invoice JSON Input", NAVY),
        ("↓", ACCENT_BLUE),
        ("[Extractor Agent]  ← Azure OpenAI GPT-4o + Pydantic", NAVY),
        ("↓", ACCENT_BLUE),
        ("[Matcher Agent]    ← Rule-based matching + RAG (FAISS + LangChain)", NAVY),
        ("↓", ACCENT_BLUE),
        ("[Exception Handler] ← Auto-approve / Block / Flag for review", NAVY),
        ("↓", ACCENT_BLUE),
        ("[SQLite DB]  +  [Streamlit UI Dashboard — 7 Pages]", NAVY),
    ]

    box_left = 1.5
    box_top = 1.15
    box_w = 10.0

    for i, (text, colour) in enumerate(flow_steps):
        is_arrow = text.strip() == "↓"
        box_h = 0.25 if is_arrow else 0.52
        shape = slide.shapes.add_shape(
            1,
            Inches(box_left), Inches(box_top),
            Inches(box_w), Inches(box_h),
        )

        if is_arrow:
            shape.fill.background()
            shape.line.fill.background()
        else:
            shape.fill.solid()
            shape.fill.fore_color.rgb = WHITE
            shape.line.color.rgb = ACCENT_BLUE
            shape.line.width = Pt(1.5)

        tf = shape.text_frame
        tf.word_wrap = False
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = text
        run.font.name = CODE_FONT if not is_arrow else BODY_FONT
        run.font.size = Pt(13) if not is_arrow else Pt(18)
        run.font.bold = not is_arrow
        run.font.color.rgb = colour

        box_top += box_h + (0.0 if is_arrow else 0.04)


def slide_06_langgraph(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 6)
    _title_box(slide, "Multi-Agent Pipeline — LangGraph StateGraph")

    sections = [
        (
            "1. Extractor Node",
            [
                "  • Calls GPT-4o for structured invoice extraction",
                "  • Validates output with Pydantic v2 (ExtractedInvoice model)",
                "  • Scores extraction confidence (0.0–1.0)",
                "  • Flags low-confidence invoices for human review",
            ],
        ),
        (
            "2. Matcher Node",
            [
                "  • Matches invoice lines to open PO lines by product_code",
                "  • Applies configurable price/qty tolerances per vendor",
                "  • Queries FAISS RAG for business rule context at match-time",
                "  • Measures latency (ms) per reconciliation run",
            ],
        ),
        (
            "3. Exception Handler Node",
            [
                "  • Classifies discrepancies: CRITICAL / WARNING / INFO",
                "  • Sets auto-action: BLOCKED / NEEDS_REVIEW / AUTO_APPROVED",
                "  • Persists exceptions and reconciliation records to SQLite",
            ],
        ),
    ]

    col_w = 4.1
    col_gap = 0.2
    top = 1.2
    h = 4.8

    for i, (heading, bullets) in enumerate(sections):
        left = 0.3 + i * (col_w + col_gap)

        # Heading box
        hdr = slide.shapes.add_shape(
            1, Inches(left), Inches(top), Inches(col_w), Inches(0.45)
        )
        hdr.fill.solid()
        hdr.fill.fore_color.rgb = NAVY
        hdr.line.fill.background()
        tf = hdr.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = heading
        run.font.name = TITLE_FONT
        run.font.bold = True
        run.font.size = Pt(14)
        run.font.color.rgb = WHITE

        # Bullets box
        body = slide.shapes.add_textbox(
            Inches(left + 0.05), Inches(top + 0.5),
            Inches(col_w - 0.1), Inches(h - 0.55),
        )
        tf2 = body.text_frame
        tf2.word_wrap = True
        for j, line in enumerate(bullets):
            p2 = tf2.paragraphs[0] if j == 0 else tf2.add_paragraph()
            p2.space_before = Pt(3)
            run2 = p2.add_run()
            run2.text = line
            run2.font.name = BODY_FONT
            run2.font.size = Pt(15)
            run2.font.color.rgb = DARK_TEXT


def slide_07_rag(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 7)
    _title_box(slide, "RAG — Retrieval-Augmented Generation on Business Rules")

    bullets = [
        "• Rule documents stored in rules/ directory as Markdown files:",
        "      reconciliation_rules.md  — core matching rules",
        "      vendor_policies.md       — per-vendor tolerance overrides",
        "      rag_training_docs.md     — enriched training context",
        "• Indexed using Azure OpenAI text-embedding-ada-002 into FAISS local vector index",
        "• Retrieved at match-time to provide context-aware rule guidance",
        "• Enables dynamic, knowledge-grounded reconciliation decisions",
    ]
    _body_textbox(slide, bullets, 0.5, 1.2, 12.33, 5.5, font_size=17)


def slide_08_rules(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 8)
    _title_box(slide, "Configurable Reconciliation Rules")

    headers = ["#", "Rule", "Description"]
    rows = [
        ["1", "QTY_TOLERANCE_STANDARD", "±5% qty variance; ±10% for -BULK SKUs"],
        ["2", "PRICE_TOLERANCE_STANDARD", "±2% price variance; ±5% when qty matches exactly"],
        ["3", "PRODUCT_CODE_EXACT_MATCH", "Case-insensitive exact product code match"],
        ["4", "NO_MATCH_BLOCK", "Unmatched product code → CRITICAL, blocked"],
        ["5", "CURRENCY_CONSISTENCY", "Invoice currency must match PO currency"],
        ["6", "CONFIDENCE_GUARDRAIL", "Confidence < 0.8 → NEEDS_HUMAN_REVIEW"],
        ["7", "AUTO_APPROVE_WITHIN_TOLERANCE", "All lines matched + confidence ≥ 0.8 → auto-approve"],
        ["8", "PARTIAL_MATCH_REVIEW", "Mixed match → PARTIAL_MATCH, WARNING raised"],
    ]
    _add_table(slide, headers, rows,
               col_widths=[0.5, 3.5, 8.2],
               left=0.3, top=1.25,
               row_height=0.46,
               header_font_size=14,
               body_font_size=13)


def slide_09_exceptions(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 9)
    _title_box(slide, "Exception Classification & Outcomes")

    headers = ["Exception", "Severity", "Auto-Action"]
    rows = [
        ["TOLERANCE_VARIANCE", "INFO", "AUTO_APPROVED"],
        ["QUANTITY_MISMATCH", "WARNING", "NEEDS_REVIEW"],
        ["PRICE_MISMATCH", "WARNING", "NEEDS_REVIEW"],
        ["NO_MATCH", "CRITICAL", "BLOCKED"],
        ["INVALID_PO", "CRITICAL", "BLOCKED"],
        ["CURRENCY_MISMATCH", "CRITICAL", "BLOCKED"],
        ["DUPLICATE_BILLING", "CRITICAL", "BLOCKED"],
        ["PARTIAL_MATCH", "WARNING", "NEEDS_REVIEW"],
    ]
    _add_table(slide, headers, rows,
               col_widths=[4.5, 2.8, 3.5],
               left=1.3, top=1.25,
               row_height=0.5,
               header_font_size=15,
               body_font_size=14,
               severity_col=1)


def slide_10_streamlit(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 10)
    _title_box(slide, "Streamlit Dashboard — 7 Pages")

    bullets = [
        "1. 🚀 Upload & Run Pipeline — Upload invoice JSON; run multi-agent pipeline with live stepper",
        "2. 🗄️  Database Explorer — Browse & filter all SQLite tables; export CSV",
        "3. 📦 Order Tracker — Invoice history, reconciliation details, pipeline logs",
        "4. ⚠️  Exceptions Dashboard — Unresolved & all exceptions; filter, resolve, export",
        "5. 🧠 RAG Management — View business rules documents loaded into FAISS index",
        "6. 📈 Observability Metrics — Mismatch rate, confidence, latency charts (Plotly)",
        "7. 🏗️  Project Architecture — Full system overview, DB schema, folder structure",
    ]
    _body_textbox(slide, bullets, 0.5, 1.2, 12.33, 5.8, font_size=17)


def slide_11_db_schema(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 11)
    _title_box(slide, "Database Schema — SQLite Tables")

    left_col = [
        "orders",
        "   Purchase Order headers",
        "order_lines",
        "   Individual PO line items",
        "invoices",
        "   Uploaded invoice headers",
        "invoice_lines",
        "   Extracted invoice line items",
        "reconciliations",
        "   Reconciliation run records",
    ]
    right_col = [
        "reconciliation_lines",
        "   Line-by-line match results",
        "exceptions",
        "   All raised exceptions with severity & auto-action",
        "invoice_templates",
        "   Template hash for drift detection",
        "pipeline_logs",
        "   Step-by-step execution logs",
        "metrics_runs",
        "   Per-run observability metrics",
    ]

    def _col(slide, items, left):
        tb = slide.shapes.add_textbox(
            Inches(left), Inches(1.2), Inches(5.8), Inches(5.8)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        for i, line in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_before = Pt(2)
            run = p.add_run()
            run.text = line
            run.font.name = CODE_FONT
            run.font.size = Pt(14)
            is_table = not line.startswith("   ")
            run.font.bold = is_table
            run.font.color.rgb = NAVY if is_table else DARK_TEXT

    _col(slide, left_col, 0.4)
    _col(slide, right_col, 6.9)


def slide_12_observability(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 12)
    _title_box(slide, "Observability & Monitoring")

    bullets = [
        "• Every pipeline run logs step-by-step entries to pipeline_logs SQLite table",
        "• Structured log entries with fields: run_id, agent, level, message, created_at",
        "• Streamlit log viewer with run_id filtering for historical run analysis",
        "• metrics_runs table tracks per-run: mismatch rate, extraction confidence, latency",
        "• Dashboard charts (Plotly): mismatch rate over time, confidence trend",
        "• UUID-based run_id for full pipeline traceability",
    ]
    _body_textbox(slide, bullets, 0.5, 1.2, 12.33, 5.5, font_size=18)


def slide_13_project_structure(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 13)
    _title_box(slide, "Project Structure")

    tree = (
        "order-recon-agentic-ai/\n"
        "├── streamlit_app/       ← UI Layer (app.py, log_viewer.py)\n"
        "├── agents/              ← LangGraph Agent Layer\n"
        "│   ├── graph.py         ← StateGraph compilation\n"
        "│   ├── nodes.py         ← 3 agent node functions\n"
        "│   └── state.py         ← ReconState TypedDict\n"
        "├── core/                ← Business Logic Layer\n"
        "│   ├── config.py        ← Env vars & Azure OpenAI client\n"
        "│   ├── db.py            ← SQLite schema & connection\n"
        "│   ├── repositories.py  ← CRUD operations\n"
        "│   ├── services.py      ← Extractor & Matcher logic\n"
        "│   ├── rules_rag.py     ← RAG engine (FAISS)\n"
        "│   ├── metrics.py       ← Observability metrics\n"
        "│   └── logger.py        ← Pipeline log persistence\n"
        "├── models/schemas.py    ← Pydantic models\n"
        "├── rules/               ← RAG Knowledge Base (Markdown)\n"
        "├── data/                ← Runtime data (git-ignored)\n"
        "├── scripts/             ← Seeding & utility scripts\n"
        "└── tests/               ← Pytest test suite"
    )

    tb = slide.shapes.add_textbox(
        Inches(0.5), Inches(1.15), Inches(12.33), Inches(6.1)
    )
    tf = tb.text_frame
    tf.word_wrap = False
    for i, line in enumerate(tree.splitlines()):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = p.add_run()
        run.text = line
        run.font.name = CODE_FONT
        run.font.size = Pt(12)
        run.font.color.rgb = DARK_TEXT


def slide_14_demo_scenarios(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 14)
    _title_box(slide, "15 Demo Invoice Scenarios")

    headers = ["#", "Scenario", "Outcome", "Severity"]
    rows = [
        ["01", "Perfect Match", "✅ MATCHED", "—"],
        ["02", "Within Tolerance", "✅ MATCHED", "INFO"],
        ["03", "Quantity Mismatch", "⚠️ MISMATCH", "WARNING"],
        ["04", "Price Mismatch", "⚠️ MISMATCH", "WARNING"],
        ["05", "No Match SKU", "🚫 BLOCKED", "CRITICAL"],
        ["06", "Invalid PO", "🚫 BLOCKED", "CRITICAL"],
        ["07", "Currency Mismatch", "🚫 BLOCKED", "CRITICAL"],
        ["08", "Duplicate Billing", "🚫 BLOCKED", "CRITICAL"],
        ["09", "Mixed Discrepancies", "⚠️ PARTIAL_MATCH", "WARNING+CRITICAL"],
        ["10-15", "Bulk / Multi-line / Strict Vendor", "✅ / ⚠️", "Various"],
    ]
    _add_table(slide, headers, rows,
               col_widths=[0.7, 3.8, 3.0, 3.3],
               left=0.8, top=1.25,
               row_height=0.47,
               header_font_size=14,
               body_font_size=13,
               severity_col=3)


def slide_15_setup(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 15)
    _title_box(slide, "Getting Started")

    steps = [
        "1.  git clone https://github.com/revanth112/order-recon-agentic-ai.git",
        "2.  python -m venv venv && source venv/bin/activate",
        "3.  pip install -r requirements.txt",
        "4.  Configure .env with Azure OpenAI credentials",
        "     (API key, endpoint, deployment names)",
        "5.  python scripts/seed_data.py",
        "     Seeds 15 demo Purchase Orders into SQLite",
        "6.  streamlit run streamlit_app/app.py",
        "     Launch the UI at http://localhost:8501",
    ]

    tb = slide.shapes.add_textbox(
        Inches(0.6), Inches(1.2), Inches(12.13), Inches(5.8)
    )
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(steps):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(4)
        run = p.add_run()
        is_code = line.strip().startswith(("git ", "python ", "pip ", "streamlit "))
        run.text = line
        run.font.name = CODE_FONT if is_code else BODY_FONT
        run.font.size = Pt(14) if is_code else Pt(16)
        run.font.color.rgb = ACCENT_BLUE if is_code else DARK_TEXT
        run.font.bold = is_code


def slide_16_summary(prs: Presentation) -> None:
    slide = _new_slide(prs)
    _add_slide_number(slide, 16)
    _title_box(slide, "Summary")

    bullets = [
        "✅  Multi-agent AI system replacing manual invoice reconciliation",
        "✅  GPT-4o powered extraction with confidence scoring",
        "✅  RAG-augmented rule-based matching with vendor tolerance policies",
        "✅  Full exception classification: CRITICAL / WARNING / INFO",
        "✅  Auto-approve / block / flag automation",
        "✅  Streamlit dashboard with 7 pages & Plotly visualizations",
        "✅  Full observability with pipeline logs and metrics",
    ]
    _body_textbox(slide, bullets, 0.5, 1.2, 12.33, 5.0, font_size=18)

    # Footer with GitHub link
    footer = slide.shapes.add_textbox(
        Inches(0.4), Inches(6.8), Inches(12.33), Inches(0.4)
    )
    tf = footer.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "GitHub: github.com/revanth112/order-recon-agentic-ai"
    run.font.name = BODY_FONT
    run.font.size = Pt(13)
    run.font.color.rgb = ACCENT_BLUE
    run.font.italic = True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_presentation(output_path: str) -> None:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    slide_01_title(prs)
    slide_02_problem(prs)
    slide_03_solution(prs)
    slide_04_tech_stack(prs)
    slide_05_architecture(prs)
    slide_06_langgraph(prs)
    slide_07_rag(prs)
    slide_08_rules(prs)
    slide_09_exceptions(prs)
    slide_10_streamlit(prs)
    slide_11_db_schema(prs)
    slide_12_observability(prs)
    slide_13_project_structure(prs)
    slide_14_demo_scenarios(prs)
    slide_15_setup(prs)
    slide_16_summary(prs)

    prs.save(output_path)
    print(f"✅  Presentation saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Order Recon Agentic AI PowerPoint presentation."
    )
    parser.add_argument(
        "--output",
        default="Order_Recon_AgenticAI_Presentation.pptx",
        help="Output file path (default: Order_Recon_AgenticAI_Presentation.pptx)",
    )
    args = parser.parse_args()
    build_presentation(args.output)
