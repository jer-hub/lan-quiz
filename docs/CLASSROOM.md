# Classroom guide

How teachers and students use LanQuiz day to day.

## Roles

| Role | How they sign in | What they do |
|------|------------------|--------------|
| **Teacher** | `/teacher/login` or register | Quizzes, classes, assignments, host games, gradebook |
| **Student** | `/student/login` | See assignments/scores; join live games with PIN + student code |
| **Guest** | No login | Join **casual** (non-assignment) games with PIN + nickname |

Students are **not** self-signup. Teachers add them to a class roster.

## Classes and roster

1. Teacher opens **Classes** → create class → note **join code** (e.g. `GNFDET`).
2. Add students: display name + `student_code` (unique **within** the class).
3. Default password = `student_code` (uppercase normalized). Optional custom password.
4. CSV import headers: `display_name,student_code[,password]`

If the same `student_code` exists in multiple classes, the student must also enter the **class join code** at login.

## Assignments (important)

An assignment links a **quiz** to a **class**. It is **not** a take-home quiz students open alone.

### Teacher flow

1. **Assignments** → pick class + quiz → optional title, due date, max attempts, score policy (`best` / `latest`).
2. **Host live game** (blocked if past due until you extend the due date).
3. Share PIN / QR; watch lobby; start questions.
4. After play: **Results** on the assignment card, or class **Gradebook** (+ CSV).

Lifecycle:

- **Open** — can host (if not overdue)
- **Close** — students see it as closed; hosting blocked
- **Reopen** — host again
- **Edit** — title, due, attempts, score policy
- **Live PIN** — shown on the card while a session is in memory

### Student flow

1. Log in → dashboard lists assignments (due, overdue, not played / score, play count).
2. When the teacher is hosting, the card shows **Live now — PIN** and a Join link.
3. Open `/play`, enter PIN + **student code** (nickname is taken from the roster).
4. Answer during the live round. Scores appear under **My scores** and in the gradebook.

Students **cannot** start an assignment quiz by themselves. That would require a future self-paced mode.

### Rules

| Rule | Behavior |
|------|----------|
| Due date | Past due → teacher cannot host until due is extended |
| Max attempts | After N completed plays for that assignment, student cannot join another session |
| Score policy | Gradebook / student summary uses **best** or **latest** score across plays |
| Closed | Hosting blocked until reopen |

## Casual games

From a quiz, **Start game** without an assignment:

- No roster required
- Players join with PIN + nickname
- Results still go to game history; not tied to gradebook assignments

## Scoring (live)

```text
points = round(BASE × (1 − (elapsed ÷ time_limit) ÷ 2))
```

Clamped to `[BASE/2, BASE]`. Wrong answers = 0. Configure `SCORE_BASE` in `.env` (default `1000`).
