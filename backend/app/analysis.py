"""Item analysis from stored per-question history."""

from __future__ import annotations

import json
from typing import Any


def analyze_questions(question_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-question % correct + distractor histogram."""
    out: list[dict[str, Any]] = []
    for q in question_history:
        results = q.get("results", []) or []
        total = len(results)
        correct = sum(1 for r in results if r.get("correct"))
        counts: dict[str, int] = {}
        for r in results:
            key = str(r.get("option_index"))
            counts[key] = counts.get(key, 0) + 1
        out.append(
            {
                "question_index": q.get("question_index"),
                "question_id": q.get("question_id"),
                "text": q.get("text", ""),
                "kind": q.get("kind", "mc"),
                "options": q.get("options", []),
                "correct_indices": q.get("correct_indices", []),
                "total": total,
                "correct": correct,
                "pct_correct": round(100.0 * correct / total, 1) if total else 0.0,
                "distractor_counts": counts,
            }
        )
    return out


def load_history_questions(row) -> list[dict[str, Any]]:
    raw = getattr(row, "questions_json", None) or "[]"
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []
