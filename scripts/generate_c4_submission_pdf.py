from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
MARGIN_X = 18 * mm
MARGIN_Y = 14 * mm

TITLE_COLOR = colors.HexColor("#0F172A")
SUBTITLE_COLOR = colors.HexColor("#475569")
ACCENT = colors.HexColor("#2563EB")
BOX_FILL = colors.HexColor("#EFF6FF")
BOX_STROKE = colors.HexColor("#1D4ED8")
GROUP_FILL = colors.HexColor("#F8FAFC")
GROUP_STROKE = colors.HexColor("#CBD5E1")
TEXT = colors.HexColor("#0F172A")


def _box(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str = "",
    *,
    fill=BOX_FILL,
    stroke=BOX_STROKE,
) -> None:
    pdf.setStrokeColor(stroke)
    pdf.setFillColor(fill)
    pdf.roundRect(x, y, w, h, 8, fill=1, stroke=1)
    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(x + w / 2, y + h - 16, title)
    if subtitle:
        pdf.setFillColor(SUBTITLE_COLOR)
        pdf.setFont("Helvetica", 9.5)
        _draw_wrapped_center(pdf, subtitle, x + w / 2, y + h - 30, w - 16, 11)


def _group(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
) -> None:
    pdf.setStrokeColor(GROUP_STROKE)
    pdf.setFillColor(GROUP_FILL)
    pdf.roundRect(x, y, w, h, 10, fill=1, stroke=1)
    pdf.setFillColor(SUBTITLE_COLOR)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x + 10, y + h - 16, label)


def _arrow(pdf: canvas.Canvas, x1: float, y1: float, x2: float, y2: float, label: str = "") -> None:
    pdf.setStrokeColor(ACCENT)
    pdf.setLineWidth(1.6)
    pdf.line(x1, y1, x2, y2)
    angle = 0
    if x2 != x1 or y2 != y1:
        from math import atan2, cos, sin

        angle = atan2(y2 - y1, x2 - x1)
        head = 7
        wing = 2.8
        pdf.line(
            x2,
            y2,
            x2 - head * cos(angle - wing),
            y2 - head * sin(angle - wing),
        )
        pdf.line(
            x2,
            y2,
            x2 - head * cos(angle + wing),
            y2 - head * sin(angle + wing),
        )
    if label:
        pdf.setFillColor(SUBTITLE_COLOR)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + 6, label)


def _draw_wrapped(pdf: canvas.Canvas, text: str, x: float, y: float, max_width: float, line_height: float) -> None:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.stringWidth(candidate, "Helvetica", 10) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    for idx, line in enumerate(lines):
        pdf.drawString(x, y - idx * line_height, line)


def _draw_wrapped_center(
    pdf: canvas.Canvas,
    text: str,
    center_x: float,
    start_y: float,
    max_width: float,
    line_height: float,
) -> None:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdf.stringWidth(candidate, "Helvetica", 9.5) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    for idx, line in enumerate(lines):
        pdf.drawCentredString(center_x, start_y - idx * line_height, line)


def _page_header(pdf: canvas.Canvas, title: str, subtitle: str) -> None:
    pdf.setFillColor(TITLE_COLOR)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 8, title)
    pdf.setFillColor(SUBTITLE_COLOR)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 26, subtitle)
    pdf.setStrokeColor(colors.HexColor("#E2E8F0"))
    pdf.setLineWidth(1)
    pdf.line(MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 34, PAGE_WIDTH - MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 34)


def _page_footer(pdf: canvas.Canvas, page_label: str) -> None:
    pdf.setStrokeColor(colors.HexColor("#E2E8F0"))
    pdf.line(MARGIN_X, MARGIN_Y + 8, PAGE_WIDTH - MARGIN_X, MARGIN_Y + 8)
    pdf.setFillColor(SUBTITLE_COLOR)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(MARGIN_X, MARGIN_Y - 2, "LocalScript - C4 submission export")
    pdf.drawRightString(PAGE_WIDTH - MARGIN_X, MARGIN_Y - 2, page_label)


def draw_title_page(pdf: canvas.Canvas) -> None:
    _page_header(pdf, "LocalScript C4 Architecture", "Single-file submission export for the platform")
    hero_x = MARGIN_X
    hero_y = 85 * mm
    hero_w = PAGE_WIDTH - 2 * MARGIN_X
    hero_h = 85 * mm
    _group(pdf, hero_x, hero_y, hero_w, hero_h, "Trust Loop Summary")
    pdf.setFillColor(TITLE_COLOR)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(hero_x + 16, hero_y + hero_h - 40, "Prompt -> LLM -> Lua extraction ->")
    pdf.drawString(hero_x + 16, hero_y + hero_h - 68, "validators -> sandbox -> retry -> response")

    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica", 11)
    bullets = [
        "Formal judged path: ollama-8gb",
        "A/B/C in the repository are evidence tracks, not separate product versions",
        "This PDF contains the three C4 levels recommended for platform upload",
    ]
    y = hero_y + hero_h - 105
    for item in bullets:
        pdf.setFillColor(ACCENT)
        pdf.circle(hero_x + 20, y + 3, 2.2, fill=1, stroke=0)
        pdf.setFillColor(TEXT)
        pdf.drawString(hero_x + 30, y, item)
        y -= 18

    pdf.setFillColor(SUBTITLE_COLOR)
    pdf.setFont("Helvetica", 10)
    _draw_wrapped(
        pdf,
        "Use this file as the single C4 deliverable for the hackathon platform. "
        "Extended architecture notes remain in docs/ARCHITECTURE_C4.md.",
        hero_x + 16,
        58 * mm,
        hero_w - 32,
        14,
    )
    _page_footer(pdf, "Page 1 / 4")
    pdf.showPage()


def draw_context_page(pdf: canvas.Canvas) -> None:
    _page_header(pdf, "Level 1 - System Context", "Who interacts with LocalScript and what stays inside the perimeter")
    left = MARGIN_X + 20
    center_y = PAGE_HEIGHT / 2 - 10
    _box(pdf, left, center_y - 25, 95, 50, "User / Judge", "Sends a natural-language request")
    _box(pdf, left + 145, center_y - 35, 140, 70, "LocalScript", "HTTP API + trust loop + evidence")
    _box(pdf, left + 340, center_y + 40, 135, 52, "Local / In-Perimeter LLM", "Ollama, vLLM or another operator-controlled endpoint")
    _box(pdf, left + 340, center_y - 20, 135, 52, "Lua Validators", "StyLua, Selene, LuaLS, luac")
    _box(pdf, left + 340, center_y - 80, 135, 52, "Optional Knowledge Corpus", "Local RAG corpus with task patterns and stubs")
    _box(pdf, left + 340, center_y - 140, 135, 52, "Sandbox Gate", "luac or Docker sandbox")
    _arrow(pdf, left + 95, center_y, left + 145, center_y)
    _arrow(pdf, left + 285, center_y + 20, left + 340, center_y + 66)
    _arrow(pdf, left + 285, center_y + 4, left + 340, center_y + 6)
    _arrow(pdf, left + 285, center_y - 12, left + 340, center_y - 54)
    _arrow(pdf, left + 285, center_y - 28, left + 340, center_y - 114)
    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica", 10)
    _draw_wrapped(
        pdf,
        "Interpretation: the user only sees LocalScript. The model, optional corpus and all checks remain "
        "inside a local or company-controlled perimeter.",
        MARGIN_X + 15,
        34 * mm,
        PAGE_WIDTH - 2 * MARGIN_X - 30,
        13,
    )
    _page_footer(pdf, "Page 2 / 4")
    pdf.showPage()


def draw_containers_page(pdf: canvas.Canvas) -> None:
    _page_header(pdf, "Level 2 - Containers", "Main runtime building blocks")
    frame_x = MARGIN_X + 10
    frame_y = 32 * mm
    frame_w = PAGE_WIDTH - 2 * MARGIN_X - 20
    frame_h = PAGE_HEIGHT - 2 * MARGIN_Y - 50
    _group(pdf, frame_x, frame_y, frame_w, frame_h, "LocalScript Runtime")

    _box(pdf, frame_x + 18, frame_y + 95, 120, 58, "FastAPI Application", "/generate, /healthz, /ui, OpenAPI")
    _box(pdf, frame_x + 170, frame_y + 95, 140, 58, "Generation Orchestrator", "Prompt assembly, retries, candidate pick, result")
    _box(pdf, frame_x + 340, frame_y + 140, 130, 52, "LLM Endpoint", "OpenAI-compatible HTTP")
    _box(pdf, frame_x + 340, frame_y + 80, 130, 52, "Validation Chain", "Static checks for generated Lua")
    _box(pdf, frame_x + 340, frame_y + 20, 130, 52, "Sandbox Gate", "luac_only or Docker")
    _box(pdf, frame_x + 170, frame_y + 15, 140, 52, "Evidence Summary", "Human-readable explanation of what ran")
    _box(pdf, frame_x + 18, frame_y + 15, 120, 52, "Optional Local RAG", "Retrieved references stay local")

    _arrow(pdf, frame_x + 138, frame_y + 124, frame_x + 170, frame_y + 124)
    _arrow(pdf, frame_x + 310, frame_y + 124, frame_x + 340, frame_y + 166)
    _arrow(pdf, frame_x + 310, frame_y + 116, frame_x + 340, frame_y + 106)
    _arrow(pdf, frame_x + 310, frame_y + 108, frame_x + 340, frame_y + 46)
    _arrow(pdf, frame_x + 170, frame_y + 40, frame_x + 138, frame_y + 40)
    _arrow(pdf, frame_x + 240, frame_y + 95, frame_x + 240, frame_y + 67)

    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica", 10)
    _draw_wrapped(
        pdf,
        "One API surface exposes compact judged mode and rich showcase mode, but both rely on the same orchestrator and the same trust loop.",
        MARGIN_X + 20,
        22 * mm,
        PAGE_WIDTH - 2 * MARGIN_X - 40,
        13,
    )
    _page_footer(pdf, "Page 3 / 4")
    pdf.showPage()


def draw_components_page(pdf: canvas.Canvas) -> None:
    _page_header(pdf, "Level 3 - Components", "How a request travels through the shared trust loop")
    cols = [MARGIN_X + 10, MARGIN_X + 145, MARGIN_X + 280, MARGIN_X + 415]
    y_top = PAGE_HEIGHT - 70 * mm
    _box(pdf, cols[0], y_top, 110, 45, "Generate Endpoint", "Accepts prompt or task/context")
    _box(pdf, cols[0], y_top - 70, 110, 45, "Input Shape Split", "Submission surface / showcase surface")
    _box(pdf, cols[1], y_top - 10, 110, 55, "Initial Message Builder", "System prompt, optional context, optional RAG")
    _box(pdf, cols[1], y_top - 95, 110, 55, "Lua Extractor", "code JSON field or fenced Lua block")
    _box(pdf, cols[2], y_top + 5, 120, 52, "Generate / Validate / Fix Loop", "LLM call, diagnostics feedback, bounded retries")
    _box(pdf, cols[2], y_top - 75, 120, 52, "Best-of-K Selector", "Optional candidate comparison")
    _box(pdf, cols[3], y_top + 20, 115, 45, "Validation Chain", "StyLua, Selene, LuaLS")
    _box(pdf, cols[3], y_top - 35, 115, 45, "Sandbox Gate", "luac or Docker")
    _box(pdf, cols[3], y_top - 90, 115, 45, "Evidence Builder", "Final trust summary")
    _box(pdf, cols[3], y_top - 145, 115, 45, "Submission / Showcase Response", "Compact code or rich response")

    _arrow(pdf, cols[0] + 110, y_top + 22, cols[1], y_top + 17)
    _arrow(pdf, cols[0] + 55, y_top, cols[0] + 55, y_top - 25)
    _arrow(pdf, cols[0] + 110, y_top - 47, cols[1], y_top - 67)
    _arrow(pdf, cols[1] + 110, y_top + 17, cols[2], y_top + 31)
    _arrow(pdf, cols[1] + 110, y_top - 67, cols[2], y_top - 49)
    _arrow(pdf, cols[2] + 120, y_top + 31, cols[3], y_top + 42)
    _arrow(pdf, cols[2] + 120, y_top + 18, cols[3], y_top - 12)
    _arrow(pdf, cols[2] + 120, y_top - 49, cols[3], y_top - 68)
    _arrow(pdf, cols[3] + 57, y_top - 90, cols[3] + 57, y_top - 100)

    pdf.setFillColor(TEXT)
    pdf.setFont("Helvetica", 9.5)
    _draw_wrapped(
        pdf,
        "Key point: submission mode and showcase mode are not separate implementations. They share the same trust loop and differ only in response shape.",
        MARGIN_X + 10,
        20 * mm,
        PAGE_WIDTH - 2 * MARGIN_X - 20,
        12,
    )
    _page_footer(pdf, "Page 4 / 4")
    pdf.showPage()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / "docs" / "C4_SUBMISSION.pdf"
    pdf = canvas.Canvas(str(output_path), pagesize=PAGE_SIZE)
    pdf.setTitle("LocalScript C4 Submission")
    pdf.setAuthor("LocalScript")
    pdf.setSubject("C4 architecture submission")
    pdf.setCreator("scripts/generate_c4_submission_pdf.py")

    draw_title_page(pdf)
    draw_context_page(pdf)
    draw_containers_page(pdf)
    draw_components_page(pdf)

    pdf.save()
    print(output_path)


if __name__ == "__main__":
    main()
