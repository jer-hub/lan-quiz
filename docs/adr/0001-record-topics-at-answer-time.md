# Record topics and correctness at answer time

Mastery is measured per topic, and an answer counts toward the topics its question had at the moment it was answered. We record those topics, and whether the answer was correct, on the answer itself rather than looking them up later, because editing a quiz replaces its questions with new ones: a later lookup would lose every answer given before the edit, and recomputing homework correctness would grade old answers against new questions.

## Consequences

- Answers given before a question was tagged never count toward mastery. Re-tagging a question changes only future answers.
- Correctness for homework attempts is fixed at submit time, so fixing a wrong answer key does not regrade past attempts.

## Considered options

- **Look up topics by question at report time.** Simpler storage, but quiz edits would orphan every earlier answer.
- **Keep question identity stable across edits.** Would let lookups work, but changes how quizzes are edited everywhere and still could not recover the topic a question had when it was answered.
