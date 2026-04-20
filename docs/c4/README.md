# C4 Export Bundle

Этот каталог хранит **исходники Mermaid** для C4-визуализации LocalScript, чтобы их можно было:

- экспортировать в PNG/SVG/PDF для платформы
- вставить в презентацию без ручной перерисовки
- держать архитектурный markdown и export sources синхронными

## Files

| File | Purpose |
|------|---------|
| `context.mmd` | System Context |
| `containers.mmd` | Container view |
| `components.mmd` | Component view |
| `sequence.mmd` | Runtime trust-loop sequence |

## Recommended export flow

1. Открыть нужный `.mmd` в редакторе с Mermaid preview.
2. Экспортировать в `PNG` или `SVG` для слайдов.
3. При необходимости собрать все четыре изображения в один PDF для площадки.

## Example with Mermaid CLI

Если установлен `mmdc`, можно экспортировать так:

```bash
mmdc -i docs/c4/context.mmd -o docs/c4/context.png
mmdc -i docs/c4/containers.mmd -o docs/c4/containers.png
mmdc -i docs/c4/components.mmd -o docs/c4/components.png
mmdc -i docs/c4/sequence.mmd -o docs/c4/sequence.png
```

## Optional single PDF (local only)

To build a **four-page** C4 PDF locally (not tracked in git by default):

- generator: [`../../scripts/generate_c4_submission_pdf.py`](../../scripts/generate_c4_submission_pdf.py) → writes `docs/C4_SUBMISSION.pdf` when run

```bash
uv run --with reportlab python scripts/generate_c4_submission_pdf.py
```

Narrative markdown for the architecture lives in [`../ARCHITECTURE_C4.md`](../ARCHITECTURE_C4.md).

## Note

Keeping Mermaid sources in git is enough for maintenance; export PNG/SVG/PDF as needed for slides or attachments without committing large binaries.
