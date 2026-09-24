import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type {
  Assignment,
  AssignmentLive,
  AssignmentResults,
  ClassOut,
  QuizSummary,
} from "../shared";

function toLocalInputValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInputValue(local: string): string | null {
  if (!local.trim()) return null;
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function formatDue(iso: string | null): string {
  if (!iso) return "No due date";
  return new Date(iso).toLocaleString();
}

type StatusFilter = "open" | "closed" | "all";

export default function AssignmentsPage() {
  const navigate = useNavigate();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [quizzes, setQuizzes] = useState<QuizSummary[]>([]);
  const [classId, setClassId] = useState("");
  const [quizId, setQuizId] = useState("");
  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [maxAttempts, setMaxAttempts] = useState("");
  const [scorePolicy, setScorePolicy] = useState("best");
  const [filter, setFilter] = useState<StatusFilter>("open");
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDue, setEditDue] = useState("");
  const [editMax, setEditMax] = useState("");
  const [editPolicy, setEditPolicy] = useState("best");
  const [resultsId, setResultsId] = useState<number | null>(null);
  const [results, setResults] = useState<AssignmentResults | null>(null);
  const [liveMap, setLiveMap] = useState<Record<number, AssignmentLive>>({});

  const load = useCallback(async () => {
    try {
      const [a, c, q] = await Promise.all([
        api.listAssignments(),
        api.listClasses(),
        api.listQuizzes(),
      ]);
      setAssignments(a);
      setClasses(c);
      setQuizzes(q);
      if (!classId && c[0]) setClassId(String(c[0].id));
      if (!quizId && q[0]) setQuizId(String(q[0].id));

      const lives = await Promise.all(
        a.filter((x) => x.status === "open").map(async (x) => {
          try {
            return [x.id, await api.getAssignmentLive(x.id)] as const;
          } catch {
            return [x.id, { active: false, pin: null, status: null, player_count: 0, quiz_title: null }] as const;
          }
        }),
      );
      const map: Record<number, AssignmentLive> = {};
      for (const [id, live] of lives) map[id] = live;
      setLiveMap(map);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [classId, quizId]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = useMemo(() => {
    if (filter === "all") return assignments;
    return assignments.filter((a) => a.status === filter);
  }, [assignments, filter]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAssignment({
        class_id: Number(classId),
        quiz_id: Number(quizId),
        title: title || undefined,
        due_at: fromLocalInputValue(dueAt),
        max_attempts: maxAttempts ? Number(maxAttempts) : null,
        score_policy: scorePolicy,
      });
      setTitle("");
      setDueAt("");
      setMaxAttempts("");
      setScorePolicy("best");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  const startEdit = (a: Assignment) => {
    setEditingId(a.id);
    setEditTitle(a.title);
    setEditDue(toLocalInputValue(a.due_at));
    setEditMax(a.max_attempts != null ? String(a.max_attempts) : "");
    setEditPolicy(a.score_policy || "best");
  };

  const saveEdit = async (id: number) => {
    try {
      const dueIso = fromLocalInputValue(editDue);
      await api.updateAssignment(id, {
        title: editTitle,
        due_at: dueIso,
        clear_due_at: !dueIso,
        max_attempts: editMax ? Number(editMax) : null,
        clear_max_attempts: !editMax,
        score_policy: editPolicy,
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const showResults = async (id: number) => {
    try {
      if (resultsId === id) {
        setResultsId(null);
        setResults(null);
        return;
      }
      setResults(await api.getAssignmentResults(id));
      setResultsId(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load results");
    }
  };

  const host = (a: Assignment) => {
    if (a.is_overdue) {
      setError("Assignment is past due. Extend the due date to host again.");
      return;
    }
    navigate(`/host/game/assignment/${a.id}`);
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="font-display text-4xl">Assignments</h1>
      <p className="mt-1 text-ink/70">
        Assign a quiz to a class, then host a live game. Students must join with their roster code.
      </p>
      {error && <p className="mt-3 text-danger">{error}</p>}

      <form
        onSubmit={(e) => void create(e)}
        className="mt-6 space-y-3 rounded-2xl border border-sky-200 bg-white p-4 shadow-sm"
      >
        <div className="flex flex-wrap gap-3">
          <label className="text-sm font-bold">
            Class
            <select
              className="mt-1 block rounded-xl border border-sky-200 px-3 py-2"
              value={classId}
              onChange={(e) => setClassId(e.target.value)}
              required
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-bold">
            Quiz
            <select
              className="mt-1 block rounded-xl border border-sky-200 px-3 py-2"
              value={quizId}
              onChange={(e) => setQuizId(e.target.value)}
              required
            >
              {quizzes.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.title}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-[180px] flex-1 text-sm font-bold">
            Title (optional)
            <input
              className="mt-1 w-full rounded-xl border border-sky-200 px-3 py-2"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm font-bold">
            Due (optional)
            <input
              type="datetime-local"
              className="mt-1 block rounded-xl border border-sky-200 px-3 py-2"
              value={dueAt}
              onChange={(e) => setDueAt(e.target.value)}
            />
          </label>
          <label className="text-sm font-bold">
            Max attempts
            <input
              type="number"
              min={1}
              max={50}
              placeholder="Unlimited"
              className="mt-1 block w-28 rounded-xl border border-sky-200 px-3 py-2"
              value={maxAttempts}
              onChange={(e) => setMaxAttempts(e.target.value)}
            />
          </label>
          <label className="text-sm font-bold">
            Score policy
            <select
              className="mt-1 block rounded-xl border border-sky-200 px-3 py-2"
              value={scorePolicy}
              onChange={(e) => setScorePolicy(e.target.value)}
            >
              <option value="best">Best score</option>
              <option value="latest">Latest score</option>
            </select>
          </label>
        </div>
        <button
          type="submit"
          disabled={!classes.length || !quizzes.length}
          className="rounded-xl bg-brand px-4 py-2.5 font-extrabold text-white disabled:opacity-50"
        >
          Create assignment
        </button>
        {!classes.length && (
          <p className="text-sm text-ink/60">
            <Link to="/teacher/classes" className="font-bold underline">
              Create a class
            </Link>{" "}
            first.
          </p>
        )}
      </form>

      <div className="mt-8 flex flex-wrap gap-2">
        {(["open", "closed", "all"] as StatusFilter[]).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-sm font-bold capitalize ${
              filter === f ? "bg-brand text-white" : "bg-sky-100 text-ink"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <ul className="mt-4 space-y-3">
        {visible.map((a) => {
          const live = liveMap[a.id];
          return (
            <li key={a.id} className="rounded-2xl border border-sky-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  {editingId === a.id ? (
                    <div className="space-y-2">
                      <input
                        className="w-full rounded-xl border border-sky-200 px-3 py-2 font-bold"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                      />
                      <div className="flex flex-wrap gap-2">
                        <input
                          type="datetime-local"
                          className="rounded-xl border border-sky-200 px-3 py-2 text-sm"
                          value={editDue}
                          onChange={(e) => setEditDue(e.target.value)}
                        />
                        <input
                          type="number"
                          min={1}
                          max={50}
                          placeholder="Max attempts"
                          className="w-28 rounded-xl border border-sky-200 px-3 py-2 text-sm"
                          value={editMax}
                          onChange={(e) => setEditMax(e.target.value)}
                        />
                        <select
                          className="rounded-xl border border-sky-200 px-3 py-2 text-sm"
                          value={editPolicy}
                          onChange={(e) => setEditPolicy(e.target.value)}
                        >
                          <option value="best">Best</option>
                          <option value="latest">Latest</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => void saveEdit(a.id)}
                          className="rounded-lg bg-brand px-3 py-2 text-sm font-extrabold text-white"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingId(null)}
                          className="rounded-lg bg-sky-100 px-3 py-2 text-sm font-bold"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <h2 className="font-display text-xl">{a.title}</h2>
                      <p className="text-sm text-ink/60">
                        {a.class_name} · {a.quiz_title} ·{" "}
                        <span className={a.status === "open" ? "text-success" : "text-ink/50"}>
                          {a.status}
                        </span>
                        {a.is_overdue && (
                          <span className="ml-2 font-bold text-danger">overdue</span>
                        )}
                      </p>
                      <p className="mt-1 text-xs text-ink/50">
                        Due: {formatDue(a.due_at)} · Attempts:{" "}
                        {a.max_attempts ?? "unlimited"} · Score: {a.score_policy || "best"}
                      </p>
                      {live?.active && live.pin && (
                        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm font-bold text-amber-950">
                          Live now — PIN{" "}
                          <span className="font-mono text-lg tracking-wider">{live.pin}</span>
                          {" · "}
                          {live.player_count} player{live.player_count === 1 ? "" : "s"} ·{" "}
                          {live.status}
                        </p>
                      )}
                    </>
                  )}
                </div>
                {editingId !== a.id && (
                  <div className="flex flex-wrap gap-2">
                    {a.status === "open" && (
                      <button
                        type="button"
                        onClick={() => host(a)}
                        disabled={!!a.is_overdue}
                        className="rounded-lg bg-brand px-3 py-2 text-sm font-extrabold text-white disabled:opacity-40"
                      >
                        Host live game
                      </button>
                    )}
                    {a.status === "open" && (
                      <button
                        type="button"
                        onClick={() => void api.closeAssignment(a.id).then(load)}
                        className="rounded-lg bg-sky-100 px-3 py-2 text-sm font-bold"
                      >
                        Close
                      </button>
                    )}
                    {a.status === "closed" && (
                      <button
                        type="button"
                        onClick={() => void api.reopenAssignment(a.id).then(load)}
                        className="rounded-lg bg-brand px-3 py-2 text-sm font-extrabold text-white"
                      >
                        Reopen
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => startEdit(a)}
                      className="rounded-lg bg-sky-100 px-3 py-2 text-sm font-bold"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => void showResults(a.id)}
                      className="rounded-lg bg-sky-100 px-3 py-2 text-sm font-bold"
                    >
                      {resultsId === a.id ? "Hide results" : "Results"}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (confirm("Delete assignment?")) void api.deleteAssignment(a.id).then(load);
                      }}
                      className="rounded-lg bg-red-50 px-3 py-2 text-sm font-bold text-danger"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
              {resultsId === a.id && results && (
                <div className="mt-4 overflow-x-auto rounded-xl border border-sky-100">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-sky-50 text-ink/70">
                      <tr>
                        <th className="px-3 py-2">Student</th>
                        <th className="px-3 py-2">Code</th>
                        <th className="px-3 py-2">Score</th>
                        <th className="px-3 py-2">Plays</th>
                        <th className="px-3 py-2">Last played</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.rows.map((r) => (
                        <tr key={r.student_id} className="border-t border-sky-100">
                          <td className="px-3 py-2 font-semibold">{r.display_name}</td>
                          <td className="px-3 py-2 font-mono">{r.student_code}</td>
                          <td className="px-3 py-2">{r.score ?? "—"}</td>
                          <td className="px-3 py-2">{r.play_count}</td>
                          <td className="px-3 py-2 text-ink/60">
                            {r.last_played_at
                              ? new Date(r.last_played_at).toLocaleString()
                              : "Not played"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </li>
          );
        })}
        {!visible.length && <li className="text-ink/50">No assignments in this filter</li>}
      </ul>
    </div>
  );
}
