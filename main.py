from __future__ import annotations

import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from agent.researcher import search_articles
from agent.summarizer import enrich_article
from agent.reporter import generate_report
from agent.post_writer import write_post_files

CONFIG_PATH = Path(__file__).parent / "config" / "topics.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    load_dotenv()

    print("=" * 60)
    print("  Fitness Research Agent")
    print("=" * 60)

    config = load_config()
    topics = config.get("topics", [])
    print(f"\n Tópicos configurados: {len(topics)}")
    print(f" Resultados por tópico: {config.get('max_results_per_topic', 3)}")

    # 1. Pesquisa
    print("\n[1/4] Buscando artigos na web...")
    articles = search_articles(config)

    if not articles:
        print("\n Nenhum artigo encontrado. Verifique sua TAVILY_API_KEY e conexão.")
        sys.exit(1)

    print(f"      {len(articles)} artigo(s) encontrado(s).")

    # 2. Sumarização
    print("\n[2/4] Sumarizando com Claude e gerando legendas para Instagram...")
    enriched_articles = []
    for i, article in enumerate(articles, start=1):
        print(f"      [{i}/{len(articles)}] {article.title[:70]}...")
        try:
            enriched = enrich_article(article)
            enriched_articles.append(enriched)
        except Exception as e:
            print(f"      AVISO: erro ao processar artigo '{article.title}': {e}")

    if not enriched_articles:
        print("\n Nenhum artigo pôde ser processado. Verifique sua ANTHROPIC_API_KEY.")
        sys.exit(1)

    # 3. Relatório
    print("\n[3/4] Gerando relatório Markdown...")
    report_path = generate_report(enriched_articles)

    # 4. Arquivos de post (caption + summary)
    print("\n[4/4] Gerando arquivos de post (caption.txt + summary.txt)...")
    for i, enriched in enumerate(enriched_articles, start=1):
        print(f"      [{i}/{len(enriched_articles)}] {enriched.title_pt[:60]}...")
        try:
            folder = write_post_files(enriched)
            print(f"      → {folder.relative_to(folder.parent.parent.parent)}")
        except Exception as e:
            print(f"      AVISO: erro ao gerar post para '{enriched.title_pt}': {e}")

    print("\n" + "=" * 60)
    print(f"  Relatório salvo em: {report_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
