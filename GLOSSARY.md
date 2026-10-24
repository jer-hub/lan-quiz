# Glossary

Terms as used in LanQuiz. Implementation details live in code and ADRs, not here.

**Quiz**
A teacher-owned set of questions with a title and description. Reusable across games and homework.

**Question**
One item in a quiz. Has a kind (multiple choice, true/false, ordering, or short answer), a time limit, and a correct answer.

**Live game**
A timed, host-run session played on a shared screen. Players join with a PIN and nickname or student code. Scored with a speed bonus.

**Host**
The teacher running a live game. Controls question flow and can reclaim the game after a page refresh.

**PIN**
The short code players type to join a live game. Unique among games in progress.

**Player**
A participant in a live game. Either a classroom student (identified by student code) or a guest (nickname only).

**Class**
A group of students owned by one teacher. Has a join code for student self-registration.

**Student code**
The roster identifier of a student within a class. Used to join classroom games. Not a secret: see the roadmap's student join identity item.

**Roster**
The list of students in a class, imported or added by hand.

**Assignment**
A quiz given to a class, either hosted live or taken as homework. Has an optional due date, attempt limit and score policy (best or latest).

**Attempt**
One student's self-paced run through an assignment's quiz. Graded without a host. Scored flat, with no speed bonus.

**Score policy**
How an assignment's repeated plays combine into a grade: `best` keeps the highest, `latest` keeps the most recent.

**Gradebook**
The per-class table of each student's score on each assignment, combining live plays and attempts.

**Item analysis**
Per-question statistics for a past live game: percentage correct and answer distribution.

## Mastery

**Topic**
A teacher-chosen label for what a question tests, such as "fractions". Groups questions across quizzes.
_Avoid_: tag, skill, category

**Accuracy**
The percentage of a student's most recent answers on a topic that were correct. Counts correctness only, never points or speed.
_Avoid_: mastery score, topic score

**Mastered**
A topic whose accuracy for a student is at or above the class's mastery threshold.
_Avoid_: passed, proficient

**Mastery threshold**
The accuracy at which a topic counts as mastered for a class. 80% unless the teacher changes it.

**Mastery report**
A teacher's per-class view of each student's accuracy on each topic, with mastered topics marked.
_Avoid_: progress report, skills report
