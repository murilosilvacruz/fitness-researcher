from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

IS_VERCEL = os.environ.get("VERCEL") == "1"

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
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


def _list_weeks() -> list[str]:
    weeks = sorted(
        [p.stem for p in REPORTS_DIR.glob("*.json") if p.stem != "read_state"],
        reverse=True,
    )
    return weeks


def _load_week(week: str) -> dict | None:
    path = REPORTS_DIR / f"{week}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/weeks")
def api_weeks():
    weeks = _list_weeks()
    read_state = _load_read_state()
    result = []
    for week in weeks:
        data = _load_week(week)
        total = len(data["articles"]) if data else 0
        read = sum(1 for a in (data["articles"] if data else []) if a["id"] in read_state)
        result.append({
            "week": week,
            "generated_at": data["generated_at"] if data else "",
            "total": total,
            "read": read,
        })
    return jsonify(result)


@app.get("/api/weeks/<week>")
def api_week_articles(week: str):
    data = _load_week(week)
    if not data:
        return jsonify({"error": "Semana não encontrada"}), 404

    read_state = _load_read_state()
    for article in data["articles"]:
        article["read"] = article["id"] in read_state

    labels = sorted({a["label"] for a in data["articles"]})
    return jsonify({"week": data["week"], "generated_at": data["generated_at"], "labels": labels, "articles": data["articles"]})


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


if __name__ == "__main__":
    app.run(debug=False, port=8080)
