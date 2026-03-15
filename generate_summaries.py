"""Backfill: gera caption.txt e summary.txt para posts já existentes sem esses arquivos.

Útil para semanas geradas antes da integração automática ao pipeline.
Uso: python generate_summaries.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent.post_writer import generate_summary, _article_id
from agent.summarizer import EnrichedArticle, _parse_response as _parse_summarizer
from agent.researcher import Article

REPORTS_DIR = Path(__file__).parent / "reports"
POSTS_DIR   = Path(__file__).parent / "posts"


def _article_from_json(data: dict) -> EnrichedArticle:
    article = Article(
        title=data["title_en"],
        url=data["url"],
        source=data["source"],
        published_date=data["published_date"],
        content="",
        label=data["label"],
    )
    return EnrichedArticle(
        article=article,
        title_pt=data["title_pt"],
        objective=data.get("objective", ""),
        conclusion=data.get("conclusion", ""),
        supporting_data=data.get("supporting_data", ""),
        instagram_caption=data.get("instagram_caption", ""),
    )


def main() -> None:
    weeks = sorted([p.name for p in POSTS_DIR.iterdir() if p.is_dir()], reverse=True)
    if not weeks:
        print("Nenhuma semana encontrada em posts/.")
        sys.exit(1)

    for week in weeks:
        report_path = REPORTS_DIR / f"{week}.json"
        if not report_path.exists():
            print(f"Relatório não encontrado para {week}, pulando.")
            continue

        report = json.loads(report_path.read_text(encoding="utf-8"))
        articles = report["articles"]
        print(f"\n── {week} — {len(articles)} artigos ──")

        for data in articles:
            folder = POSTS_DIR / week / data["id"]
            folder.mkdir(parents=True, exist_ok=True)

            enriched = _article_from_json(data)
            any_written = False

            caption_path = folder / "caption.txt"
            if not caption_path.exists():
                caption_path.write_text(enriched.instagram_caption, encoding="utf-8")
                print(f"  ✓ caption.txt  [{data['id']}]")
                any_written = True

            summary_path = folder / "summary.txt"
            if not summary_path.exists():
                summary = generate_summary(enriched)
                summary_path.write_text(summary, encoding="utf-8")
                print(f"  ✓ summary.txt  [{data['id']}] {data['title_pt'][:50]}...")
                any_written = True

            if not any_written:
                print(f"  [skip] {data['id']} — arquivos já existem")


if __name__ == "__main__":
    main()
