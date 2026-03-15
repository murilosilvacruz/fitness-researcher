from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from agent.researcher import Article

CLAUDE_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """\
Você é uma assistente especializada em ciência do exercício, com foco em musculação e saúde feminina.
Você apoia uma personal trainer brasileira que atende exclusivamente mulheres não atletas — \
praticantes recreativas de musculação, mulheres sedentárias que estão começando a se exercitar, \
ou mulheres ativas da população geral, de qualquer idade.
Seu objetivo é transformar artigos científicos e notícias em conteúdo acessível, confiável e útil \
para esse público específico.
IMPORTANTE: Artigos focados exclusivamente em atletas de alto rendimento, competidoras profissionais \
ou esportistas de elite não são relevantes para este público. Se o estudo envolver apenas atletas, \
sinalize isso claramente e avalie se os achados têm aplicabilidade para mulheres não atletas.
Sempre escreva em português do Brasil, de forma clara e direta.\
"""

SUMMARY_PROMPT = """\
Analise o artigo abaixo e retorne exatamente no seguinte formato (sem texto antes ou depois):

TITULO_PT:
[Traduza o título para o português. Se já estiver em português, mantenha-o.]

OBJETIVO:
[1 parágrafo descrevendo o objetivo do artigo e a hipótese investigada. \
Se o estudo foi conduzido exclusivamente com atletas de alto rendimento ou competidoras profissionais, \
inicie o parágrafo com a tag [ESTUDO EM ATLETAS] e explique brevemente se os achados podem ou não \
ser extrapolados para mulheres não atletas.]

CONCLUSAO:
[1 parágrafo com a principal conclusão do estudo, contextualizada para mulheres não atletas sempre que possível.]

DADOS:
[1 parágrafo com os dados, números ou evidências que sustentam a conclusão.]

LEGENDA_INSTAGRAM:
[Legenda para Instagram com até 2200 caracteres. \
Tom: próximo, motivador e educativo, como uma personal trainer falando com suas alunas — \
mulheres comuns, não atletas, de qualquer idade. \
Inclua: gancho inicial impactante, explicação do assunto de forma simples, aplicação prática no dia a dia, \
chamada para ação (ex: salvar, comentar, marcar uma amiga). \
Se o estudo foi feito com atletas mas tem aplicabilidade para a população geral, adapte a linguagem \
para esse contexto sem distorcer os resultados. \
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
