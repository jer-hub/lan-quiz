# Sample quizzes

Import these from the teacher UI (**Import**) or via `POST /api/quizzes/import` with a JSON body.

| File | Description |
|------|-------------|
| [`sample-quiz.json`](sample-quiz.json) | Short demo (LAN / Socket.IO / true-false / multi-correct) |
| [`friday-night-trivia.json`](friday-night-trivia.json) | Longer party-style trivia set |

## JSON shape

```json
{
  "title": "Quiz title",
  "description": "Optional blurb",
  "questions": [
    {
      "text": "Question text",
      "image": null,
      "options": ["A", "B", "C", "D"],
      "correct_indices": [0],
      "time_limit": 20
    }
  ]
}
```

| Field | Rules |
|-------|--------|
| `options` | 2–6 non-empty strings |
| `correct_indices` | 0-based indices into `options` (one or more) |
| `time_limit` | Seconds, typically 5–120 |
| `image` | Optional data URL or null (MVP often null) |
