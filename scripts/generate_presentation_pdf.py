from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
MARGIN_X = 18 * mm
MARGIN_Y = 12 * mm

TITLE_COLOR = colors.HexColor("#0F172A")
TEXT_COLOR = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
ACCENT = colors.HexColor("#2563EB")
SOFT_ACCENT = colors.HexColor("#EFF6FF")
LINE = colors.HexColor("#CBD5E1")
LIGHT = colors.HexColor("#F8FAFC")
FONT_REGULAR = "ArialMTCustom"
FONT_BOLD = "ArialBoldCustom"


@dataclass
class Slide:
    title: str
    subtitle: str = ""
    bullets: list[str] | None = None
    callout: str | None = None
    custom: str | None = None


SLIDES: list[Slide] = [
    Slide(
        title="LocalScript",
        subtitle="Локальный контур доверия для генерации Lua-кода",
        bullets=[
            "OpenAI-compatible LLM в вашем периметре + валидация + sandbox",
            "локальный или in-perimeter runtime path",
            "открытый репозиторий + воспроизводимая проверка",
        ],
        callout="Не просто генерация кода, а проверяемый pipeline с evidence.",
    ),
    Slide(
        title="Проблема",
        bullets=[
            "в secure / integration perimeter нельзя отправлять код и промпты внешним AI-вендорам",
            "lightweight local model без проверяющего контура дает нестабильный результат",
            "нужен управляемый цикл генерации, проверки и доработки",
        ],
        callout="Задача не в том, чтобы “сделать чат-бота для Lua”, а в том, чтобы построить локальный контур доверенной генерации кода.",
    ),
    Slide(
        title="Решение",
        bullets=[
            "natural language request на русском или английском",
            "local / in-perimeter OpenAI-compatible LLM",
            "Lua extraction, validators, sandbox, retry loop",
            "compact judged path и rich showcase path на одном ядре",
        ],
        callout="Prompt -> local/in-perimeter LLM -> Lua extraction -> validators -> sandbox -> retry -> response",
    ),
    Slide(
        title="Почему это не чат, а trust loop",
        bullets=[
            "ценность не в первом ответе модели",
            "ценность в цикле: generation -> validation -> correction",
            "если проверки не выполнялись, система показывает это честно",
            "качество строится вокруг evidence, а не вокруг “магии модели”",
        ],
        callout="Мы оцениваем не строку от LLM, а итоговый проверенный артефакт.",
    ),
    Slide(title="Архитектура", subtitle="C4: пользователь, API, оркестратор, проверки", custom="architecture"),
    Slide(
        title="Один движок, два интерфейса",
        bullets=[
            "submission surface: prompt -> code",
            "showcase surface: task/context -> steps + validation + evidence",
            "judged-friendly compact path не требует отдельной реализации",
            "демо-поверхность нужна для прозрачности, а не для второго продукта",
        ],
        callout="Один trust loop, два формата ответа.",
    ),
    Slide(
        title="Почему Lua-коду можно доверять",
        bullets=[
            "validation chain: StyLua, Selene, LuaLS, luac",
            "syntax / sandbox gate встроен в product pipeline",
            "automated tests и smoke paths проверяют поведение системы",
            "frozen compact JSON фиксируют, какие проверки реально прошли",
        ],
        callout="LocalScript проверяет не только генерацию, но и итоговый технический артефакт.",
    ),
    Slide(
        title="Агентность и итерации",
        bullets=[
            "система умеет выдать первый рабочий вариант",
            "система умеет дорабатывать результат по обратной связи",
            "retry loop поддержан архитектурно и виден в showcase response",
            "в live demo это показывается как первый запрос + уточняющий второй запрос",
        ],
        callout="Итерация здесь — управляемый процесс, а не разовый prompt engineering.",
    ),
    Slide(title="Дорожки доказательств A / B / C", custom="tracks"),
    Slide(
        title="Формальный путь под бриф",
        bullets=[
            "профиль: ollama-8gb",
            "модель: qwen2.5-coder:7b",
            "num_ctx=4096, num_predict=256, batch=1, parallel=1",
            "без RAG и quality layers, sandbox = luac_only",
        ],
        callout="Официальная judged line = track B / ollama-8gb.",
    ),
    Slide(title="Метрики и воспроизводимость", custom="metrics"),
    Slide(
        title="Честные ограничения и продуктовая ценность",
        bullets=[
            "luac_only легче и ближе к judged profile, но слабее Docker sandbox",
            "optional layers не подменяют formal path",
            "локальность обеспечивается deployment-моделью и внутренним контуром",
            "ценность: безопасная генерация Lua в закрытом контуре, меньше ручной переписки, выше объяснимость и воспроизводимость",
        ],
        callout="LocalScript — это локальный, воспроизводимый и проверяемый контур работы с кодом в среде, где данные не должны покидать периметр компании.",
    ),
]


def draw_header(pdf: canvas.Canvas, slide: Slide, index: int, total: int) -> None:
    pdf.setFillColor(TITLE_COLOR)
    pdf.setFont(FONT_BOLD, 24)
    pdf.drawString(MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 8, slide.title)
    if slide.subtitle:
        pdf.setFillColor(MUTED)
        pdf.setFont(FONT_REGULAR, 11)
        pdf.drawString(MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 28, slide.subtitle)
    pdf.setStrokeColor(LINE)
    pdf.line(MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 36, PAGE_WIDTH - MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 36)
    pdf.setFillColor(MUTED)
    pdf.setFont(FONT_REGULAR, 9)
    pdf.drawRightString(PAGE_WIDTH - MARGIN_X, PAGE_HEIGHT - MARGIN_Y - 12, f"{index} / {total}")


def draw_footer(pdf: canvas.Canvas) -> None:
    pdf.setStrokeColor(LINE)
    pdf.line(MARGIN_X, MARGIN_Y + 10, PAGE_WIDTH - MARGIN_X, MARGIN_Y + 10)
    pdf.setFillColor(MUTED)
    pdf.setFont(FONT_REGULAR, 9)
    pdf.drawString(MARGIN_X, MARGIN_Y - 2, "LocalScript presentation export")


def draw_bullets(pdf: canvas.Canvas, bullets: list[str], x: float, y: float, width: float) -> None:
    cursor_y = y
    for bullet in bullets:
        pdf.setFillColor(ACCENT)
        pdf.circle(x + 3, cursor_y + 3, 2.2, fill=1, stroke=0)
        pdf.setFillColor(TEXT_COLOR)
        pdf.setFont(FONT_REGULAR, 12)
        cursor_y = draw_wrapped_text(pdf, bullet, x + 12, cursor_y, width - 16, 16, font_size=12) - 12


def draw_wrapped_text(
    pdf: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    line_height: float,
    *,
    font_name: str = FONT_REGULAR,
    font_size: int = 12,
) -> float:
    pdf.setFont(font_name, font_size)
    words = text.split()
    line = ""
    lines: list[str] = []
    for word in words:
        candidate = f"{line} {word}".strip()
        if not line or pdf.stringWidth(candidate, font_name, font_size) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    for idx, current in enumerate(lines):
        pdf.drawString(x, y - idx * line_height, current)
    return y - len(lines) * line_height


def draw_callout(pdf: canvas.Canvas, text: str) -> None:
    x = MARGIN_X
    y = 24 * mm
    w = PAGE_WIDTH - 2 * MARGIN_X
    h = 26 * mm
    pdf.setFillColor(SOFT_ACCENT)
    pdf.setStrokeColor(ACCENT)
    pdf.roundRect(x, y, w, h, 8, fill=1, stroke=1)
    pdf.setFillColor(ACCENT)
    pdf.setFont(FONT_BOLD, 11)
    pdf.drawString(x + 12, y + h - 14, "Ключевая мысль")
    pdf.setFillColor(TEXT_COLOR)
    draw_wrapped_text(pdf, text, x + 12, y + h - 30, w - 24, 14, font_size=11)


def draw_architecture(pdf: canvas.Canvas) -> None:
    boxes = [
        (MARGIN_X + 10, 120 * mm, 60 * mm, 20 * mm, "Пользователь / Жюри"),
        (MARGIN_X + 85 * mm, 120 * mm, 75 * mm, 24 * mm, "LocalScript API"),
        (MARGIN_X + 175 * mm, 120 * mm, 80 * mm, 24 * mm, "Generation Orchestrator"),
        (MARGIN_X + 175 * mm, 84 * mm, 80 * mm, 22 * mm, "Validation Chain"),
        (MARGIN_X + 175 * mm, 52 * mm, 80 * mm, 22 * mm, "Sandbox Gate"),
        (MARGIN_X + 270 * mm, 120 * mm, 78 * mm, 24 * mm, "OpenAI-compatible LLM"),
        (MARGIN_X + 270 * mm, 84 * mm, 78 * mm, 22 * mm, "Optional Local RAG"),
        (MARGIN_X + 270 * mm, 52 * mm, 78 * mm, 22 * mm, "Evidence Summary"),
    ]
    for x, y, w, h, label in boxes:
        pdf.setFillColor(SOFT_ACCENT)
        pdf.setStrokeColor(ACCENT)
        pdf.roundRect(x, y, w, h, 6, fill=1, stroke=1)
        pdf.setFillColor(TEXT_COLOR)
        pdf.setFont(FONT_BOLD, 11)
        pdf.drawCentredString(x + w / 2, y + h / 2 - 4, label)

    pdf.setStrokeColor(ACCENT)
    pdf.line(MARGIN_X + 70 * mm, 130 * mm, MARGIN_X + 85 * mm, 130 * mm)
    pdf.line(MARGIN_X + 160 * mm, 130 * mm, MARGIN_X + 175 * mm, 130 * mm)
    pdf.line(MARGIN_X + 255 * mm, 130 * mm, MARGIN_X + 270 * mm, 130 * mm)
    pdf.line(MARGIN_X + 215 * mm, 120 * mm, MARGIN_X + 215 * mm, 106 * mm)
    pdf.line(MARGIN_X + 215 * mm, 84 * mm, MARGIN_X + 215 * mm, 74 * mm)
    pdf.line(MARGIN_X + 255 * mm, 95 * mm, MARGIN_X + 270 * mm, 95 * mm)
    pdf.line(MARGIN_X + 255 * mm, 63 * mm, MARGIN_X + 270 * mm, 63 * mm)

    pdf.setFillColor(MUTED)
    draw_wrapped_text(
        pdf,
        "Пользователь видит только LocalScript. Модель, optional retrieval и все проверки остаются внутри локального или корпоративного контура.",
        MARGIN_X,
        34 * mm,
        PAGE_WIDTH - 2 * MARGIN_X,
        14,
        font_size=11,
    )


def draw_tracks(pdf: canvas.Canvas) -> None:
    x = MARGIN_X
    y = 120 * mm
    w = PAGE_WIDTH - 2 * MARGIN_X
    row_h = 20 * mm
    col_w = [28 * mm, 45 * mm, w - 73 * mm]

    headers = ["Track", "Profile", "Что доказывает"]
    rows = [
        ("A", "qwen7b-local-benchmark", "engineering-max local path: RAG, Docker sandbox, richer validation"),
        ("B", "ollama-8gb", "формальное judged proof path по брифу"),
        ("C", "instruct-research", "исследовательский ceiling качества, не часть formal compliance"),
    ]
    draw_table(pdf, x, y, col_w, row_h, headers, rows)
    draw_callout(pdf, "A / B / C — это evidence tracks, а не три разные версии продукта. Официальная judged line = B.")


def draw_metrics(pdf: canvas.Canvas) -> None:
    x = MARGIN_X
    y = 116 * mm
    col_w = [52 * mm, 34 * mm, 34 * mm, 34 * mm]
    row_h = 15 * mm
    headers = ["Track", "Success", "Avg sec", "Max sec"]
    rows = [
        ("Formal remote B", "8/8", "4.13", "26.57"),
        ("Warm remote B", "8/8", "0.37", "0.61"),
        ("Local benchmark A", "8/8", "1.95", "3.81"),
    ]
    draw_table(pdf, x, y, col_w, row_h, headers, rows)
    draw_callout(
        pdf,
        "У нас есть reproducible runbook, smoke script и frozen compact JSON. Cold-start на remote path честно зафиксирован отдельно и не маскируется.",
    )


def draw_table(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    col_widths: list[float],
    row_height: float,
    headers: list[str],
    rows: list[tuple[str, ...]],
) -> None:
    current_y = y
    total_w = sum(col_widths)
    pdf.setFillColor(ACCENT)
    pdf.setStrokeColor(ACCENT)
    pdf.rect(x, current_y, total_w, row_height, fill=1, stroke=1)
    cursor_x = x
    pdf.setFillColor(colors.white)
    pdf.setFont(FONT_BOLD, 11)
    for idx, header in enumerate(headers):
        pdf.drawString(cursor_x + 6, current_y + row_height / 2 - 4, header)
        cursor_x += col_widths[idx]
    current_y -= row_height

    for row_index, row in enumerate(rows):
        pdf.setFillColor(LIGHT if row_index % 2 == 0 else colors.white)
        pdf.setStrokeColor(LINE)
        pdf.rect(x, current_y, total_w, row_height, fill=1, stroke=1)
        cursor_x = x
        pdf.setFillColor(TEXT_COLOR)
        pdf.setFont(FONT_REGULAR, 10.5)
        for idx, cell in enumerate(row):
            draw_wrapped_text(pdf, cell, cursor_x + 6, current_y + row_height - 12, col_widths[idx] - 12, 11, font_size=10)
            cursor_x += col_widths[idx]
        current_y -= row_height


def draw_slide(pdf: canvas.Canvas, slide: Slide, index: int, total: int) -> None:
    draw_header(pdf, slide, index, total)
    if slide.custom == "architecture":
        draw_architecture(pdf)
    elif slide.custom == "tracks":
        draw_tracks(pdf)
    elif slide.custom == "metrics":
        draw_metrics(pdf)
    else:
        if slide.bullets:
            draw_bullets(pdf, slide.bullets, MARGIN_X, 122 * mm, PAGE_WIDTH - 2 * MARGIN_X)
        if slide.callout:
            draw_callout(pdf, slide.callout)
    draw_footer(pdf)
    pdf.showPage()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_path = root / "docs" / "PRESENTATION_SUBMISSION.pdf"
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, "/System/Library/Fonts/Supplemental/Arial.ttf"))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
    pdf = canvas.Canvas(str(output_path), pagesize=PAGE_SIZE)
    pdf.setTitle("LocalScript Presentation")
    pdf.setAuthor("LocalScript")
    pdf.setSubject("Hackathon project presentation")
    pdf.setCreator("scripts/generate_presentation_pdf.py")

    total = len(SLIDES)
    for idx, slide in enumerate(SLIDES, start=1):
        draw_slide(pdf, slide, idx, total)

    pdf.save()
    print(output_path)


if __name__ == "__main__":
    main()
