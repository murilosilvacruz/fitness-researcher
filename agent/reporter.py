from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from agent.summarizer import EnrichedArticle

REPORTS_DIR = Path(__file__).parent.parent / "reports"


def _week_label() -> str:
    now = datetime.now()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def generate_report(articles: list[EnrichedArticle]) -> Path:
    """Gera o relatório semanal em Markdown e JSON, retorna o caminho do Markdown."""
    REPORTS_DIR.mkdir(exist_ok=True)

    week = _week_label()
    report_path = REPORTS_DIR / f"{week}.md"
    json_path = REPORTS_DIR / f"{week}.json"

    now_iso = datetime.now().isoformat(timespec="seconds")
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")

    # ── JSON ──────────────────────────────────────────────────────────────
    json_data = {
        "week": week,
        "generated_at": now_iso,
        "articles": [
            {
                "id": _article_id(e.article.url),
                "title_pt": e.title_pt,
                "title_en": e.article.title,
                "url": e.article.url,
                "source": e.article.source,
                "published_date": e.article.published_date,
                "label": e.article.label,
                "objective": e.objective,
                "conclusion": e.conclusion,
                "supporting_data": e.supporting_data,
                "instagram_caption": e.instagram_caption,
            }
            for e in articles
        ],
    }
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Markdown ──────────────────────────────────────────────────────────
    lines: list[str] = [
        f"# Relatório de Pesquisa — {week}",
        "",
        f"Gerado em {now_str} | {len(articles)} artigo(s) encontrado(s)",
        "",
        "---",
        "",
    ]

    by_label: dict[str, list[EnrichedArticle]] = {}
    for enriched in articles:
        by_label.setdefault(enriched.article.label, []).append(enriched)

    for label, items in by_label.items():
        lines.append(f"## {label}")
        lines.append("")

        for enriched in items:
            art = enriched.article
            lines += [
                f"### {enriched.title_pt}",
                f"*{art.title}*",
                "",
                f"- **Fonte:** [{art.source}]({art.url})",
                f"- **Publicado em:** {art.published_date}",
                f"- **Label:** `{art.label}`",
                "",
                "#### Objetivo e Hipótese",
                "",
                enriched.objective,
                "",
                "#### Conclusão",
                "",
                enriched.conclusion,
                "",
                "#### Dados de Suporte",
                "",
                enriched.supporting_data,
                "",
            ]

            if enriched.instagram_caption:
                lines += [
                    "#### Sugestão de Legenda para Instagram",
                    "",
                    "```",
                    enriched.instagram_caption,
                    "```",
                    "",
                ]

            lines += ["---", ""]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
