# Sample quizzes

Import these from the teacher UI (**Import**) or via `POST /api/quizzes/import` with a JSON body.

| File | Description |
|------|-------------|
| [`sample-quiz.json`](sample-quiz.json) | Short demo (LAN / Socket.IO / true-false / multi-correct) |
| [`friday-night-trivia.json`](friday-night-trivia.json) | Longer party-style trivia set |

## Sample roster

[`sample-roster.csv`](sample-roster.csv) — class import with required headers in order:
`username,password,first_name,last_name,email,school_id,class_section`.

## Sample teachers

[`sample-teachers.csv`](sample-teachers.csv) — same headers, teacher-only
`POST /api/auth/teachers/import` (logged-in teacher). Only
`username`/`password` are used; blank password defaults to username.

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
