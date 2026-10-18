import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import type { AttemptDetail } from "../shared";

export default function AttemptPage() {
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<AttemptDetail | null>(null);
  const [answers, setAnswers] = useState<
    Record<number, { option_index?: number | null; answer_text?: string; order?: number[] }>
  >({});
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ score: number; total: number; correct_count: number } | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setDetail(await api.getAttempt(Number(attemptId)));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load attempt");
      }
    })();
  }, [attemptId]);

  if (error) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <p className="font-display text-3xl text-danger">Something went wrong</p>
        <p className="mt-2">{error}</p>
        <Link to="/student" className="mt-6 inline-block font-bold text-brand-dark underline">
          Back
        </Link>
      </div>
    );
  }
  if (!detail) return <p className="p-8 text-ink/60">Loading…</p>;
  if (done) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10 text-center">
        <h1 className="font-display text-4xl">Submitted</h1>
        <p className="mt-2 text-2xl font-extrabold text-brand-dark">
          {done.correct_count}/{detail.quiz.questions.length} correct · {done.score}/{done.total} pts
        </p>
        <button
          type="button"
          onClick={() => navigate("/student")}
          className="mt-6 rounded-xl bg-brand px-5 py-3 font-extrabold text-white"
        >
          Back to assignments
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="font-display text-3xl">{detail.quiz.title}</h1>
      <p className="mt-1 text-ink/60">{detail.assignment.title} · homework (no host needed)</p>
      <div className="mt-6 space-y-6">
        {detail.quiz.questions.map((q) => (
          <div key={q.order_index} className="rounded-2xl border border-sky-200 bg-white p-5">
            <p className="font-bold">
              Q{q.order_index + 1}. {q.text}
            </p>
            {q.kind === "short_answer" ? (
              <input
                className="mt-3 w-full rounded-xl border border-sky-200 px-3 py-2"
                value={answers[q.order_index]?.answer_text || ""}
                onChange={(e) =>
                  setAnswers((p) => ({ ...p, [q.order_index]: { answer_text: e.target.value } }))
                }
                placeholder="Type your answer"
              />
            ) : q.kind === "ordering" ? (
              <div className="mt-3 grid gap-2">
                <p className="text-xs text-ink/50">Tap the options from first to last.</p>
                {q.options.map((opt, i) => {
                  const place = (answers[q.order_index]?.order || []).indexOf(i);
                  return (
                    <button
                      key={i}
                      type="button"
                      disabled={place >= 0}
                      onClick={() =>
                        setAnswers((p) => ({
                          ...p,
                          [q.order_index]: {
                            order: [...(p[q.order_index]?.order || []), i],
                          },
                        }))
                      }
                      className={`rounded-xl px-3 py-2 text-left font-semibold ${
                        place >= 0 ? "bg-brand text-white" : "bg-sky-50"
                      }`}
                    >
                      {place >= 0 ? `#${place + 1} ` : ""}
                      {opt}
                    </button>
                  );
                })}
                {(answers[q.order_index]?.order || []).length > 0 && (
                  <button
                    type="button"
                    className="justify-self-start text-xs underline"
                    onClick={() =>
                      setAnswers((p) => ({ ...p, [q.order_index]: { order: [] } }))
                    }
                  >
                    Start over
                  </button>
                )}
              </div>
            ) : (
              <div className="mt-3 grid gap-2">
                {q.options.map((opt, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setAnswers((p) => ({ ...p, [q.order_index]: { option_index: i } }))}
                    className={`rounded-xl px-3 py-2 text-left font-semibold ${
                      answers[q.order_index]?.option_index === i
                        ? "bg-brand text-white"
                        : "bg-sky-50"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() =>
          void (async () => {
            try {
              const payload = detail.quiz.questions.map((q) => ({
                order_index: q.order_index,
                question_id: q.question_id,
                option_index: answers[q.order_index]?.option_index ?? null,
                answer_text: answers[q.order_index]?.answer_text ?? null,
                order: answers[q.order_index]?.order ?? null,
              }));
              const res = await api.submitAttempt(Number(attemptId), payload);
              setDone({ score: res.score, total: res.total, correct_count: res.correct_count });
            } catch (e) {
              setError(e instanceof Error ? e.message : "Submit failed");
            }
          })()
        }
        className="mt-6 w-full rounded-2xl bg-brand py-4 text-xl font-extrabold text-white"
      >
        Submit homework
      </button>
    </div>
  );
}
