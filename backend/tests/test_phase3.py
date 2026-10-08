"""Phase 3: analysis math, upload guards, roster import shape."""

from app.analysis import analyze_questions


def test_analyze_pct_and_histogram():
    hist = [
        {
            "question_index": 0,
            "question_id": 1,
            "text": "2+2?",
            "kind": "mc",
            "options": ["3", "4"],
            "correct_indices": [1],
            "results": [
                {"sid": "a", "correct": True, "option_index": 1},
                {"sid": "b", "correct": False, "option_index": 0},
                {"sid": "c", "correct": True, "option_index": 1},
                {"sid": "d", "correct": False, "option_index": None},
            ],
        }
    ]
    (row,) = analyze_questions(hist)
    assert row["total"] == 4
    assert row["correct"] == 2
    assert row["pct_correct"] == 50.0
    assert row["distractor_counts"] == {"1": 2, "0": 1, "None": 1}


def test_analyze_empty():
    assert analyze_questions([]) == []
    (row,) = analyze_questions(
        [{"question_index": 0, "results": [], "options": [], "correct_indices": []}]
    )
    assert row["pct_correct"] == 0.0
