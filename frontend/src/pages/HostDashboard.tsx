import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { QuizSummary } from "../shared";

export default function HostDashboard() {
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);
  const teacherFileRef = useRef<HTMLInputElement>(null);
  const [teacherReport, setTeacherReport] = useState<{
    added: number;
    skipped: Array<{ row: number; reason: string }>;
  } | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setQuizzes(await api.listQuizzes());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load quizzes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onDelete = async (id: number, title: string) => {
    if (
      !confirm(
        `Delete quiz “${title}”?\n\nAny assignments that use this quiz will also be removed. Game history scores are kept.`,
      )
    ) {
      return;
    }
    try {
      setError(null);
      await api.deleteQuiz(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const onExport = async (id: number, title: string) => {
    try {
      const data = await api.exportQuiz(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title.replace(/[^\w\-]+/g, "_").toLowerCase() || "quiz"}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  const onImportFile = async (file: File) => {
    try {
      const text = await file.text();
      const json = JSON.parse(text);
      await api.importQuiz(json);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    }
  };

  const onImportTeachers = async (file: File) => {
    try {
      setTeacherReport(null);
      const res = await api.importTeachers(file);
      setTeacherReport({ added: res.added.length, skipped: res.skipped });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Teacher import failed");
    }
  };

  const downloadTeacherTemplate = () => {
    const blob = new Blob(
      [
        "username,password,first_name,last_name,email,school_id,class_section\njsmith,,Jane,Smith,jane@school.edu,T001,\n",
      ],
      { type: "text/csv" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "teachers-template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl text-ink">Host dashboard</h1>
          <p className="mt-1 text-ink/70">Create quizzes, then start a live LanQuiz session.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="rounded-xl border border-sky-300 bg-white px-4 py-2.5 font-bold text-ink transition hover:bg-sky-50"
          >
            Import JSON
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onImportFile(f);
              e.target.value = "";
            }}
          />
          <Link
            to="/host/quizzes/new"
            className="rounded-xl bg-brand px-4 py-2.5 font-extrabold text-white shadow transition hover:bg-brand-dark"
          >
            New quiz
          </Link>
          <button
            type="button"
            onClick={() => teacherFileRef.current?.click()}
            className="rounded-xl border border-sky-300 bg-white px-4 py-2.5 font-bold text-ink transition hover:bg-sky-50"
          >
            Import teachers
          </button>
          <input
            ref={teacherFileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onImportTeachers(f);
              e.target.value = "";
            }}
          />
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-ink/60">
        <span>
          Teacher CSV: same headers as roster (
          <span className="font-mono">username,…,class_section</span>) — only
          username/password are used.
        </span>
        <button type="button" onClick={downloadTeacherTemplate} className="font-bold underline">
          Template
        </button>
      </div>
      {teacherReport && (
        <div className="mb-4 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm">
          <p className="font-bold">
            Imported {teacherReport.added} teacher{teacherReport.added === 1 ? "" : "s"}
            {teacherReport.skipped.length > 0 && ` · ${teacherReport.skipped.length} skipped`}
          </p>
          {teacherReport.skipped.length > 0 && (
            <ul className="mt-2 space-y-1">
              {teacherReport.skipped.slice(0, 10).map((s, i) => (
                <li key={i} className="text-ink/70">
                  Row {s.row}: {s.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-800" role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-ink/60">Loading quizzes…</p>
      ) : quizzes.length === 0 ? (
        <div className="rounded-3xl border-2 border-dashed border-sky-300 bg-white/60 px-6 py-16 text-center">
          <p className="font-display text-2xl">No quizzes yet</p>
          <p className="mt-2 text-ink/70">Create your first quiz or import a JSON file.</p>
          <Link
            to="/host/quizzes/new"
            className="mt-6 inline-block rounded-xl bg-accent px-5 py-3 font-extrabold text-ink"
          >
            Create quiz
          </Link>
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {quizzes.map((q) => (
            <li
              key={q.id}
              className="animate-slide-up rounded-2xl border border-sky-200 bg-white p-5 shadow-sm transition hover:shadow-md"
            >
              <h2 className="font-display text-2xl leading-tight">{q.title}</h2>
              <p className="mt-1 line-clamp-2 text-sm text-ink/65">{q.description || "No description"}</p>
              <p className="mt-3 text-sm font-semibold text-brand-dark">
                {q.question_count} question{q.question_count === 1 ? "" : "s"}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  to={`/host/game/${q.id}`}
                  className="rounded-lg bg-brand px-3 py-2 text-sm font-extrabold text-white hover:bg-brand-dark"
                >
                  Start game
                </Link>
                <Link
                  to={`/host/quizzes/${q.id}`}
                  className="rounded-lg bg-sky-100 px-3 py-2 text-sm font-bold text-ink hover:bg-sky-200"
                >
                  Edit
                </Link>
                <button
                  type="button"
                  onClick={() => void onExport(q.id, q.title)}
                  className="rounded-lg bg-sky-100 px-3 py-2 text-sm font-bold text-ink hover:bg-sky-200"
                >
                  Export
                </button>
                <button
                  type="button"
                  onClick={() => void onDelete(q.id, q.title)}
                  className="rounded-lg bg-red-50 px-3 py-2 text-sm font-bold text-danger hover:bg-red-100"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
