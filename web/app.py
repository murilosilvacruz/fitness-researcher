from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

IS_VERCEL = os.environ.get("VERCEL") == "1"

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
POSTS_DIR = BASE_DIR / "posts"
READ_STATE_FILE = REPORTS_DIR / "read_state.json"

app = Flask(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_read_state() -> set[str]:
    if READ_STATE_FILE.exists():
        return set(json.loads(READ_STATE_FILE.read_text(encoding="utf-8")))
    return set()


def _save_read_state(state: set[str]) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    READ_STATE_FILE.write_text(json.dumps(sorted(state), ensure_ascii=False, indent=2), encoding="utf-8")


def _list_runs() -> list[str]:
    return sorted(
        [p.stem for p in REPORTS_DIR.glob("*.json") if p.stem != "read_state"],
        reverse=True,
    )


def _load_run(date: str) -> dict | None:
    path = REPORTS_DIR / f"{date}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/runs")
def api_runs():
    runs = _list_runs()
    read_state = _load_read_state()
    result = []
    for date in runs:
        data = _load_run(date)
        total = len(data["articles"]) if data else 0
        read = sum(1 for a in (data["articles"] if data else []) if a["id"] in read_state)
        result.append({
            "date": date,
            "generated_at": data["generated_at"] if data else "",
            "total": total,
            "read": read,
        })
    return jsonify(result)


@app.get("/api/runs/<date>")
def api_run_articles(date: str):
    data = _load_run(date)
    if not data:
        return jsonify({"error": "Pesquisa não encontrada"}), 404

    read_state = _load_read_state()
    for article in data["articles"]:
        article["read"] = article["id"] in read_state
        post_folder = POSTS_DIR / date / article["id"]
        eval_data = _load_eval(post_folder)
        article["published_instagram"] = eval_data.get("published_instagram", False) if eval_data else False
        article["has_background"] = (post_folder / "background.png").exists()

    labels = sorted({a["label"] for a in data["articles"]})
    return jsonify({"date": data["date"], "generated_at": data["generated_at"], "labels": labels, "articles": data["articles"]})


@app.post("/api/articles/<article_id>/read")
def api_mark_read(article_id: str):
    body = request.get_json(silent=True) or {}
    is_read: bool = body.get("read", True)
    state = _load_read_state()
    if is_read:
        state.add(article_id)
    else:
        state.discard(article_id)
    _save_read_state(state)
    return jsonify({"id": article_id, "read": is_read})


_research_process: subprocess.Popen | None = None


@app.post("/api/research/run")
def api_run_research():
    if IS_VERCEL:
        return jsonify({
            "status": "unavailable",
            "message": "A pesquisa automática não está disponível nesta versão. Execute python3 main.py localmente.",
        }), 503

    global _research_process
    if _research_process and _research_process.poll() is None:
        return jsonify({"status": "running", "message": "Pesquisa já em andamento."}), 409

    _research_process = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "main.py")],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return jsonify({"status": "started", "message": "Pesquisa iniciada!"})


@app.get("/api/research/status")
def api_research_status():
    if IS_VERCEL:
        return jsonify({"status": "unavailable"})
    if _research_process is None:
        return jsonify({"status": "idle"})
    code = _research_process.poll()
    if code is None:
        return jsonify({"status": "running"})
    return jsonify({"status": "done", "exit_code": code})


# ── Review Queue (Fila de Publicação) ─────────────────────────────────────────

def _load_eval(post_folder: Path) -> dict | None:
    path = post_folder / "eval.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_post_files(post_folder: Path) -> dict:
    summary = ""
    caption = ""
    summary_path = post_folder / "summary.txt"
    caption_path = post_folder / "caption.txt"
    if summary_path.exists():
        summary = summary_path.read_text(encoding="utf-8")
    if caption_path.exists():
        caption = caption_path.read_text(encoding="utf-8")
    return {"summary": summary, "caption": caption}


@app.get("/api/posts")
def api_list_posts():
    """Lista todos os posts com seus status de eval, opcionalmente filtrados por status."""
    status_filter = request.args.get("status")
    posts = []

    if not POSTS_DIR.exists():
        return jsonify([])

    for date_dir in sorted(POSTS_DIR.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for article_dir in sorted(date_dir.iterdir()):
            if not article_dir.is_dir():
                continue
            eval_data = _load_eval(article_dir)
            post_status = eval_data.get("status", "NO_EVAL") if eval_data else "NO_EVAL"

            if status_filter and post_status != status_filter:
                continue

            files = _load_post_files(article_dir)
            has_image = (article_dir / "image.png").exists()

            posts.append({
                "id": article_dir.name,
                "date": date_dir.name,
                "status": post_status,
                "has_image": has_image,
                "summary": files["summary"],
                "caption": files["caption"],
                "eval": eval_data,
            })

    return jsonify(posts)


@app.get("/api/posts/<date>/<post_id>")
def api_get_post(date: str, post_id: str):
    """Retorna os detalhes completos de um post específico."""
    post_folder = POSTS_DIR / date / post_id
    if not post_folder.exists():
        return jsonify({"error": "Post não encontrado"}), 404

    files = _load_post_files(post_folder)
    eval_data = _load_eval(post_folder)
    has_image = (post_folder / "image.png").exists()

    return jsonify({
        "id": post_id,
        "date": date,
        "status": eval_data.get("status", "NO_EVAL") if eval_data else "NO_EVAL",
        "has_image": has_image,
        "summary": files["summary"],
        "caption": files["caption"],
        "eval": eval_data,
    })


@app.post("/api/posts/<date>/<post_id>/approve")
def api_approve_post(date: str, post_id: str):
    """Aprova um post para publicação."""
    post_folder = POSTS_DIR / date / post_id
    eval_path = post_folder / "eval.json"

    if not post_folder.exists():
        return jsonify({"error": "Post não encontrado"}), 404

    eval_data: dict = {}
    if eval_path.exists():
        try:
            eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    eval_data["status"] = "APPROVED"
    eval_data.setdefault("notes", "")
    eval_path.write_text(json.dumps(eval_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"id": post_id, "date": date, "status": "APPROVED"})


@app.post("/api/posts/<date>/<post_id>/reject")
def api_reject_post(date: str, post_id: str):
    """Rejeita um post com nota opcional."""
    post_folder = POSTS_DIR / date / post_id
    eval_path = post_folder / "eval.json"

    if not post_folder.exists():
        return jsonify({"error": "Post não encontrado"}), 404

    body = request.get_json(silent=True) or {}
    notes = body.get("notes", "")

    eval_data: dict = {}
    if eval_path.exists():
        try:
            eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    eval_data["status"] = "REJECTED"
    eval_data["notes"] = notes
    eval_path.write_text(json.dumps(eval_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"id": post_id, "date": date, "status": "REJECTED", "notes": notes})


@app.get("/api/posts/<date>/<post_id>/background")
def api_post_background(date: str, post_id: str):
    """Serve o background.png de um post."""
    bg_path = POSTS_DIR / date / post_id / "background.png"
    if not bg_path.exists():
        return jsonify({"error": "Imagem não encontrada"}), 404
    return send_file(bg_path, mimetype="image/png")


@app.post("/api/posts/<date>/<post_id>/published")
def api_toggle_published(date: str, post_id: str):
    """Marca ou desmarca um post como publicado no Instagram."""
    post_folder = POSTS_DIR / date / post_id
    eval_path = post_folder / "eval.json"

    if not post_folder.exists():
        return jsonify({"error": "Post não encontrado"}), 404

    body = request.get_json(silent=True) or {}
    published: bool = body.get("published", True)

    eval_data: dict = {}
    if eval_path.exists():
        try:
            eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    eval_data["published_instagram"] = published
    eval_path.write_text(json.dumps(eval_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({"id": post_id, "date": date, "published_instagram": published})


@app.get("/api/posts/stats")
def api_posts_stats():
    """Retorna contagem de posts por status."""
    stats: dict[str, int] = {
        "APPROVED": 0,
        "PENDING_REVIEW": 0,
        "REJECTED": 0,
        "NO_EVAL": 0,
    }

    if not POSTS_DIR.exists():
        return jsonify(stats)

    for date_dir in POSTS_DIR.iterdir():
        if not date_dir.is_dir():
            continue
        for article_dir in date_dir.iterdir():
            if not article_dir.is_dir():
                continue
            eval_data = _load_eval(article_dir)
            status = eval_data.get("status", "NO_EVAL") if eval_data else "NO_EVAL"
            stats[status] = stats.get(status, 0) + 1

    return jsonify(stats)


if __name__ == "__main__":
    app.run(debug=False, port=8080)
