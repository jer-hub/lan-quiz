import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import AiQuizGenerator from "../components/AiQuizGenerator";
import type { Question } from "../shared";

const emptyQuestion = (): Question => ({
  text: "",
  image: null,
  options: ["", "", "", ""],
  correct_indices: [0],
  time_limit: 20,
});

export default function QuizEditor() {
  const { id } = useParams();
  const isNew = !id || id === "new";
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [questions, setQuestions] = useState<Question[]>([emptyQuestion()]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(!isNew);

  useEffect(() => {
    if (isNew) return;
    const quizId = Number(id);
    void (async () => {
      try {
        const quiz = await api.getQuiz(quizId);
        setTitle(quiz.title);
        setDescription(quiz.description);
        setQuestions(
          quiz.questions.map((q) => ({
            text: q.text,
            image: q.image,
            options: q.options,
            correct_indices: q.correct_indices,
            time_limit: q.time_limit,
          })),
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load quiz");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isNew]);

  const updateQuestion = (index: number, patch: Partial<Question>) => {
    setQuestions((prev) => prev.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  };

  const updateOption = (qi: number, oi: number, value: string) => {
    setQuestions((prev) =>
      prev.map((q, i) => {
        if (i !== qi) return q;
        const options = [...q.options];
        options[oi] = value;
        return { ...q, options };
      }),
    );
  };

  const toggleCorrect = (qi: number, oi: number) => {
    setQuestions((prev) =>
      prev.map((q, i) => {
        if (i !== qi) return q;
        const set = new Set(q.correct_indices);
        if (set.has(oi)) {
          if (set.size > 1) set.delete(oi);
        } else {
          set.add(oi);
        }
        return { ...q, correct_indices: [...set].sort((a, b) => a - b) };
      }),
    );
  };

  const addOption = (qi: number) => {
    setQuestions((prev) =>
      prev.map((q, i) => {
        if (i !== qi || q.options.length >= 6) return q;
        return { ...q, options: [...q.options, ""] };
      }),
    );
  };

  const removeOption = (qi: number, oi: number) => {
    setQuestions((prev) =>
      prev.map((q, i) => {
        if (i !== qi || q.options.length <= 2) return q;
        const options = q.options.filter((_, idx) => idx !== oi);
        const correct_indices = q.correct_indices
          .filter((c) => c !== oi)
          .map((c) => (c > oi ? c - 1 : c));
        return {
          ...q,
          options,
          correct_indices: correct_indices.length ? correct_indices : [0],
        };
      }),
    );
  };

  const onImage = async (qi: number, file: File | null) => {
    if (!file) {
      updateQuestion(qi, { image: null });
      return;
    }
    if (file.size > 1_500_000) {
      setError("Image too large (max ~1.5 MB)");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      updateQuestion(qi, { image: String(reader.result) });
    };
    reader.readAsDataURL(file);
  };

  const save = async () => {
    setError(null);
    setSaving(true);
    try {
      const body = { title: title.trim(), description: description.trim(), questions };
      if (isNew) {
        const created = await api.createQuiz(body);
        navigate(`/host/quizzes/${created.id}`, { replace: true });
      } else {
        await api.updateQuiz(Number(id), body);
        navigate("/host");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="p-8 text-ink/60">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between gap-3">
        <h1 className="font-display text-4xl">{isNew ? "New quiz" : "Edit quiz"}</h1>
        <Link to="/host" className="font-semibold text-brand-dark hover:underline">
          Back
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-800" role="alert">
          {error}
        </div>
      )}

      <AiQuizGenerator
        onGenerated={(quiz) => {
          setError(null);
          setTitle(quiz.title);
          setDescription(quiz.description);
          setQuestions(
            quiz.questions.length
              ? quiz.questions.map((q) => ({
                  text: q.text,
                  image: q.image ?? null,
                  options: q.options,
                  correct_indices: q.correct_indices,
                  time_limit: q.time_limit || 20,
                }))
              : [emptyQuestion()],
          );
        }}
      />

      <div className="space-y-4 rounded-2xl border border-sky-200 bg-white p-5 shadow-sm">
        <label className="block">
          <span className="mb-1 block text-sm font-bold">Title</span>
          <input
            className="w-full rounded-xl border border-sky-200 px-3 py-2.5"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Friday Trivia"
            required
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-bold">Description</span>
          <textarea
            className="w-full rounded-xl border border-sky-200 px-3 py-2.5"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional notes for the host"
          />
        </label>
      </div>

      <div className="mt-6 space-y-6">
        {questions.map((q, qi) => (
          <div key={qi} className="rounded-2xl border border-sky-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-xl">Question {qi + 1}</h2>
              {questions.length > 1 && (
                <button
                  type="button"
                  className="text-sm font-bold text-danger"
                  onClick={() => setQuestions((prev) => prev.filter((_, i) => i !== qi))}
                >
                  Remove
                </button>
              )}
            </div>
            <textarea
              className="mb-3 w-full rounded-xl border border-sky-200 px-3 py-2.5"
              rows={2}
              value={q.text}
              onChange={(e) => updateQuestion(qi, { text: e.target.value })}
              placeholder="Question text"
            />
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <label className="text-sm font-bold">
                Time (s){" "}
                <input
                  type="number"
                  min={5}
                  max={120}
                  className="ml-1 w-20 rounded-lg border border-sky-200 px-2 py-1"
                  value={q.time_limit}
                  onChange={(e) => updateQuestion(qi, { time_limit: Number(e.target.value) || 20 })}
                />
              </label>
              <label className="text-sm font-bold">
                Image{" "}
                <input
                  type="file"
                  accept="image/*"
                  className="ml-1 text-sm font-normal"
                  onChange={(e) => void onImage(qi, e.target.files?.[0] || null)}
                />
              </label>
              {q.image && (
                <button
                  type="button"
                  className="text-sm font-bold text-danger"
                  onClick={() => updateQuestion(qi, { image: null })}
                >
                  Clear image
                </button>
              )}
            </div>
            {q.image && (
              <img src={q.image} alt="" className="mb-3 max-h-40 rounded-xl object-contain" />
            )}
            <p className="mb-2 text-sm font-bold text-ink/70">
              Options — tap the check to mark correct (one or more)
            </p>
            <ul className="space-y-2">
              {q.options.map((opt, oi) => (
                <li key={oi} className="flex items-center gap-2">
                  <button
                    type="button"
                    aria-label={q.correct_indices.includes(oi) ? "Correct" : "Mark correct"}
                    aria-pressed={q.correct_indices.includes(oi)}
                    onClick={() => toggleCorrect(qi, oi)}
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg font-bold text-white ${
                      q.correct_indices.includes(oi) ? "bg-success" : "bg-slate-300"
                    }`}
                  >
                    ✓
                  </button>
                  <input
                    className="min-w-0 flex-1 rounded-xl border border-sky-200 px-3 py-2"
                    value={opt}
                    onChange={(e) => updateOption(qi, oi, e.target.value)}
                    placeholder={`Option ${oi + 1}`}
                  />
                  {q.options.length > 2 && (
                    <button
                      type="button"
                      className="px-2 font-bold text-ink/50 hover:text-danger"
                      onClick={() => removeOption(qi, oi)}
                      aria-label="Remove option"
                    >
                      ×
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {q.options.length < 6 && (
              <button
                type="button"
                className="mt-3 text-sm font-bold text-brand-dark"
                onClick={() => addOption(qi)}
              >
                + Add option
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => setQuestions((prev) => [...prev, emptyQuestion()])}
          className="rounded-xl border border-sky-300 bg-white px-4 py-2.5 font-bold"
        >
          Add question
        </button>
        <button
          type="button"
          disabled={saving || !title.trim()}
          onClick={() => void save()}
          className="rounded-xl bg-brand px-5 py-2.5 font-extrabold text-white disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save quiz"}
        </button>
      </div>
    </div>
  );
}
