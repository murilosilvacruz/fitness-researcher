from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import anthropic

from agent.summarizer import EnrichedArticle
from agent.reporter import _article_id
from agent.evaluator import evaluate_post, EvalResult

logger = logging.getLogger(__name__)

POSTS_DIR = Path(__file__).parent.parent / "posts"

_SYSTEM = """\
Você é a voz editorial da marca Corpo e Saber — uma marca brasileira de conteúdo científico \
sobre saúde e treino para mulheres de 30 a 55 anos, com foco especial em mulheres de 40 a 55 anos \
(perimenopausa, saúde óssea, qualidade de vida).

Voz da marca: inteligente, direta e acolhedora. Trata a leitora como adulta capaz de entender \
ciência. Nunca infantilizada, nunca alarmista, nunca com jargão técnico sem tradução.
Escreva sempre em português do Brasil.\
"""

_PROMPT = """\
Com base nas informações do artigo científico abaixo, crie o texto para a imagem do post \
do Instagram da marca Corpo e Saber com EXATAMENTE este formato (sem texto fora do formato):

TITULO:
[Frase impactante com no máximo 60 caracteres. Conte os caracteres com cuidado. \
Prefira afirmações surpreendentes a perguntas. Nunca use ponto de exclamação. \
Capture o achado científico mais relevante para mulheres 40+.]

SUBTITULO:
[Frase complementar com o mecanismo ou número-chave. Máximo 150 caracteres.]

PILAR:
[Selecione o pilar mais adequado para este conteúdo: CIÊNCIA EM DOSE | SEU CORPO EXPLICA | \
NA PRÁTICA | O DADO QUE IMPORTA | MITO OU VERDADE | MOVIMENTO LIVRE | MENTE E CORPO]

BULLETS:
[De 2 a 4 pontos para carousel. Cada ponto em uma linha, começando com •. \
Cada ponto deve ser uma afirmação curta e direta (máximo 120 caracteres), \
apresentando um dado, mecanismo ou aplicação prática do artigo. \
Escreva exatamente 2, 3 ou 4 bullets — nunca mais do que 4.]

---
Título: {title_pt}
Label: {label}
Objetivo: {objective}
Conclusão: {conclusion}
Dados: {supporting_data}\
"""


_PILAR_VISUALS: dict[str, str] = {
    "CIÊNCIA EM DOSE": (
        "woman in her 40s doing strength training or stretching in a bright home studio, "
        "back or partial silhouette only, warm natural light, empowering and calm mood"
    ),
    "SEU CORPO EXPLICA": (
        "close-up of a woman's arms or legs mid-movement — lifting, stretching or walking, "
        "soft focus, organic natural tones, editorial feel"
    ),
    "NA PRÁTICA": (
        "woman actively exercising at home or outdoors — squatting, using resistance bands "
        "or doing bodyweight movements, partial frame showing body from neck down, natural light"
    ),
    "O DADO QUE IMPORTA": (
        "woman walking or jogging on a quiet path at golden hour, silhouette or back view, "
        "sense of consistency and routine, warm earth tones"
    ),
    "MITO OU VERDADE": (
        "two women of different activity levels side by side in a natural outdoor setting, "
        "back or partial view only, soft contrast between stillness and movement"
    ),
    "MOVIMENTO LIVRE": (
        "woman in joyful motion outdoors — dancing, hiking or stretching freely in nature, "
        "blurred movement, golden hour light, sense of freedom and lightness"
    ),
    "MENTE E CORPO": (
        "woman in a serene yoga or breathing pose, soft natural light through window or outdoors, "
        "calm and grounded atmosphere, back or silhouette only"
    ),
}

_DEFAULT_VISUAL = (
    "woman in her 40s in gentle movement — walking, stretching or doing light exercise "
    "in a natural or home setting, back or partial view, warm soft light"
)

_IMAGE_PROMPT_TEMPLATE = """\
Generate a high-quality background image for an Instagram post (1080x1080 px).

Brand: Corpo e Saber — Brazilian science-based health content for women 40+.
Topic: {title}
Detail: {subtitle}

Visual direction: {visual}

Style requirements:
- No text, numbers or legible words anywhere in the image
- No faces visible (back, silhouettes, partial frames or hands only)
- Avoid laboratory equipment, microscopes, petri dishes or research props
- Prioritize real women in movement over abstract or still-life compositions
- Color palette: warm off-white (#F7F5F2), terracotta (#C9614A) accents, muted earth tones
- Mood: calm, trustworthy, empowering, editorial
- Lighting: soft, diffused, natural — avoid harsh shadows or neon
- Composition: leave generous negative space in the center for text overlay
- Format: square 1:1, photorealistic or high-quality digital art
"""


def _generate_image_prompt(title: str, subtitle: str, pilar: str) -> str:
    """Monta o prompt para geração de imagem de fundo via Gemini ou similar."""
    visual = _PILAR_VISUALS.get(pilar.upper().strip(), _DEFAULT_VISUAL)
    return _IMAGE_PROMPT_TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        visual=visual,
    ).strip()


def _date_label() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _parse_response(text: str) -> dict:
    result: dict = {"title": "", "subtitle": "", "pilar": "", "bullets": []}
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
        elif stripped == "PILAR:":
            if current == "subtitle":
                result["subtitle"] = " ".join(buffer).strip()
            current = "pilar"; buffer = []
        elif stripped == "BULLETS:":
            if current == "pilar":
                result["pilar"] = " ".join(buffer).strip()
            current = "bullets"; buffer = []
        elif current == "bullets" and stripped.startswith("•"):
            result["bullets"].append(stripped)
        elif current and current != "bullets" and stripped:
            buffer.append(stripped)

    if current == "pilar":
        result["pilar"] = " ".join(buffer).strip()
    elif current == "subtitle":
        result["subtitle"] = " ".join(buffer).strip()

    return result


def _format_summary(data: dict) -> str:
    lines = [
        f"TITULO: {data['title']}",
        f"SUBTITULO: {data['subtitle']}",
    ]
    if data.get("pilar"):
        lines.append(f"PILAR: {data['pilar']}")
    bullets = data.get("bullets") or []
    if bullets:
        lines.append("BULLETS:")
        lines.extend(bullets[:4])
    return "\n".join(lines)


def generate_summary(enriched: EnrichedArticle) -> tuple[str, dict]:
    """Chama o Claude e retorna (conteúdo formatado para summary.txt, dict parseado)."""
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
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    parsed = _parse_response(raw)
    return _format_summary(parsed), parsed


def write_post_files(enriched: EnrichedArticle, date: str | None = None) -> tuple[Path, EvalResult]:
    """Cria a pasta do artigo, escreve caption.txt e summary.txt, e roda evals.

    Retorna tupla (pasta, EvalResult).
    """
    if date is None:
        date = _date_label()

    article_id = _article_id(enriched.article.url)
    folder = POSTS_DIR / date / article_id
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "caption.txt").write_text(
        enriched.instagram_caption or "", encoding="utf-8"
    )

    summary, parsed = generate_summary(enriched)
    (folder / "summary.txt").write_text(summary, encoding="utf-8")

    image_prompt = _generate_image_prompt(
        title=parsed.get("title") or enriched.title_pt,
        subtitle=parsed.get("subtitle") or enriched.conclusion,
        pilar=parsed.get("pilar", ""),
    )
    (folder / "image_prompt.txt").write_text(image_prompt, encoding="utf-8")

    eval_result = evaluate_post(folder)
    logger.info(
        "Eval post %s: status=%s auto_score=%.2f%s",
        article_id,
        eval_result.status,
        eval_result.auto.score,
        f" llm_score={eval_result.llm.score_normalized:.2f}" if eval_result.llm else "",
    )

    return folder, eval_result
