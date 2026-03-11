from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from tavily import TavilyClient


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_date: str
    content: str
    label: str
    score: float = 0.0


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.removeprefix("www.")
    except Exception:
        return url


def search_articles(config: dict[str, Any]) -> list[Article]:
    """Busca artigos recentes para todos os tópicos configurados."""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    topics: list[dict] = config.get("topics", [])
    trusted_domains: list[str] = config.get("trusted_domains", [])
    max_results: int = config.get("max_results_per_topic", 3)

    # Busca apenas conteúdo publicado nos últimos 7 dias
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    seen_urls: set[str] = set()
    articles: list[Article] = []

    for topic in topics:
        query: str = topic["query"]
        label: str = topic.get("label", "Geral")

        results = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=trusted_domains if trusted_domains else None,
            include_answer=False,
        )

        for result in results.get("results", []):
            url: str = result.get("url", "")
            if not url or url in seen_urls:
                continue

            published = result.get("published_date") or cutoff
            content = result.get("content", "").strip()
            if not content:
                continue

            seen_urls.add(url)
            articles.append(
                Article(
                    title=result.get("title", "Sem título"),
                    url=url,
                    source=_extract_domain(url),
                    published_date=published,
                    content=content,
                    label=label,
                    score=result.get("score", 0.0),
                )
            )

    # Ordena pelos mais relevantes primeiro e aplica limite global
    articles.sort(key=lambda a: a.score, reverse=True)
    max_total: int = config.get("max_total_articles", 10)
    return articles[:max_total]
