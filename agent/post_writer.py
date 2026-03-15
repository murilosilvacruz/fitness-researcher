from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import anthropic

from agent.summarizer import EnrichedArticle
from agent.reporter import _article_id

POSTS_DIR = Path(__file__).parent.parent / "posts"

_SYSTEM = """\
Você é uma personal trainer brasileira especializada em saúde feminina e musculação.
Escreva em português do Brasil, de forma direta, motivadora e acessível.\
"""

_PROMPT = """\
Com base nas informações do artigo científico abaixo, crie um resumo para publicação \
no Instagram com EXATAMENTE este formato (sem texto fora do formato):

TITULO:
[Título impactante com no máximo 60 caracteres. Conte os caracteres com cuidado.]

SUBTITULO:
[Subtítulo complementar com no máximo 150 caracteres.]

BULLETS:
[Inclua 2 ou 3 bullet points somente se acrescentarem informação relevante não \
coberta pelo título e subtítulo. Cada bullet: no máximo 100 caracteres, começando \
com "• ". Se não houver nada relevante a acrescentar, deixe esta seção vazia.]

---
Título: {title_pt}
Label: {label}
Objetivo: {objective}
Conclusão: {conclusion}
Dados: {supporting_data}\
"""


def _week_label() -> str:
    now = datetime.now()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _parse_response(text: str) -> dict:
    result: dict = {"title": "", "subtitle": "", "bullets": []}
    current = None
    buffer: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "TITULO:":
            current = "title"; buffer = []
        elif stripped == "SUBTITULO:":
            if current == "title":
                result["title"] = " ".join(buffer).strip()
            current = "subtitle"; buffer = []
        elif stripped == "BULLETS:":
            if current == "subtitle":
                result["subtitle"] = " ".join(buffer).strip()
            current = "bullets"; buffer = []
        elif current and stripped:
            buffer.append(stripped)

    if current == "bullets":
        result["bullets"] = [b for b in buffer if b.startswith("•")]
    elif current == "subtitle":
        result["subtitle"] = " ".join(buffer).strip()

    return result


def _format_summary(data: dict) -> str:
    lines = [
        f"TITULO: {data['title']}",
        f"SUBTITULO: {data['subtitle']}",
    ]
    if data["bullets"]:
        lines.append("BULLETS:")
        lines.extend(data["bullets"])
    return "\n".join(lines)


def generate_summary(enriched: EnrichedArticle) -> str:
    """Chama o Claude e retorna o conteúdo formatado para summary.txt."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = _PROMPT.format(
        title_pt=enriched.title_pt,
        label=enriched.article.label,
        objective=enriched.objective,
        conclusion=enriched.conclusion,
        supporting_data=enriched.supporting_data,
    )

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    return _format_summary(_parse_response(raw))


def write_post_files(enriched: EnrichedArticle, week: str | None = None) -> Path:
    """Cria a pasta do artigo e escreve caption.txt e summary.txt.

    Retorna o caminho da pasta criada.
    """
    if week is None:
        week = _week_label()

    article_id = _article_id(enriched.article.url)
    folder = POSTS_DIR / week / article_id
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "caption.txt").write_text(
        enriched.instagram_caption or "", encoding="utf-8"
    )

    summary = generate_summary(enriched)
    (folder / "summary.txt").write_text(summary, encoding="utf-8")

    return folder
