from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from agent.researcher import Article

CLAUDE_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """\
Você é uma assistente especializada em ciência do exercício, com foco em musculação e saúde feminina.
Você apoia uma personal trainer brasileira que atende principalmente mulheres.
Seu objetivo é transformar artigos científicos e notícias em conteúdo acessível, confiável e útil.
Sempre escreva em português do Brasil, de forma clara e direta.\
"""

SUMMARY_PROMPT = """\
Analise o artigo abaixo e retorne exatamente no seguinte formato (sem texto antes ou depois):

TITULO_PT:
[Traduza o título para o português. Se já estiver em português, mantenha-o.]

OBJETIVO:
[1 parágrafo descrevendo o objetivo do artigo e a hipótese investigada.]

CONCLUSAO:
[1 parágrafo com a principal conclusão do estudo.]

DADOS:
[1 parágrafo com os dados, números ou evidências que sustentam a conclusão.]

LEGENDA_INSTAGRAM:
[Legenda para Instagram com até 2200 caracteres. \
Tom: próximo, motivador e educativo, como uma personal trainer falando com suas alunas. \
Inclua: gancho inicial impactante, explicação do assunto de forma simples, aplicação prática, \
chamada para ação (ex: salvar, comentar, marcar uma amiga). \
Adicione 5 a 10 hashtags relevantes ao final.]

---
Título original: {title}
Fonte: {source}
Conteúdo:
{content}\
"""


@dataclass
class EnrichedArticle:
    article: Article
    title_pt: str
    objective: str
    conclusion: str
    supporting_data: str
    instagram_caption: str


def enrich_article(article: Article) -> EnrichedArticle:
    """Gera resumo estruturado e legenda de Instagram para um artigo usando o Claude."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = SUMMARY_PROMPT.format(
        title=article.title,
        source=article.source,
        content=article.content[:8000],
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    return _parse_response(article, raw)


def _parse_response(article: Article, text: str) -> EnrichedArticle:
    """Extrai os campos estruturados do texto retornado pelo Claude."""
    sections = {
        "TITULO_PT": "",
        "OBJETIVO": "",
        "CONCLUSAO": "",
        "DADOS": "",
        "LEGENDA_INSTAGRAM": "",
    }

    current = None
    buffer: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        matched = False
        for key in sections:
            if stripped == f"{key}:":
                if current:
                    sections[current] = "\n".join(buffer).strip()
                current = key
                buffer = []
                matched = True
                break
        if not matched and current:
            buffer.append(line)

    if current:
        sections[current] = "\n".join(buffer).strip()

    return EnrichedArticle(
        article=article,
        title_pt=sections["TITULO_PT"] or article.title,
        objective=sections["OBJETIVO"],
        conclusion=sections["CONCLUSAO"],
        supporting_data=sections["DADOS"],
        instagram_caption=sections["LEGENDA_INSTAGRAM"],
    )
