import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../hooks/useAuth";
import type { Assignment, AssignmentLive } from "../shared";

function formatDue(iso: string | null): string {
  if (!iso) return "No due date";
  return new Date(iso).toLocaleString();
}

export default function StudentDashboard() {
  const { displayName, className } = useAuth();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [scores, setScores] = useState<Array<Record<string, unknown>>>([]);
  const [showClosed, setShowClosed] = useState(false);
  const [liveMap, setLiveMap] = useState<Record<number, AssignmentLive>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [asg, sc] = await Promise.all([api.listMyAssignments(), api.myScores()]);
        setAssignments(asg);
        setScores(sc);
        const open = asg.filter((a) => a.status === "open");
        const lives = await Promise.all(
          open.map(async (a) => {
            try {
              return [a.id, await api.getAssignmentLive(a.id)] as const;
            } catch {
              return [
                a.id,
                { active: false, pin: null, status: null, player_count: 0, quiz_title: null },
              ] as const;
            }
          }),
        );
        const map: Record<number, AssignmentLive> = {};
        for (const [id, live] of lives) map[id] = live;
        setLiveMap(map);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    })();
  }, []);

  const visible = useMemo(() => {
    if (showClosed) return assignments;
    return assignments.filter((a) => a.status === "open" || a.is_overdue);
  }, [assignments, showClosed]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="font-display text-4xl">Hi, {displayName}</h1>
      <p className="mt-1 text-ink/70">{className}</p>
      {error && <p className="mt-3 text-danger">{error}</p>}

      <div className="mt-6">
        <Link
          to="/play"
          className="inline-block rounded-2xl bg-brand px-5 py-3 font-extrabold text-white"
        >
          Join live game
        </Link>
      </div>

      <section className="mt-10">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-2xl">Assignments</h2>
          <label className="flex items-center gap-2 text-sm font-semibold text-ink/70">
            <input
              type="checkbox"
              checked={showClosed}
              onChange={(e) => setShowClosed(e.target.checked)}
            />
            Show closed
          </label>
        </div>
        <ul className="mt-3 space-y-2">
          {visible.map((a) => {
            const live = liveMap[a.id];
            const statusLabel = a.played
              ? `${a.score_policy === "latest" ? "Latest" : "Best"} score ${a.best_score ?? 0} · ${a.play_count ?? 0} play${(a.play_count ?? 0) === 1 ? "" : "s"}`
              : "Not played";
            return (
              <li key={a.id} className="rounded-xl border border-sky-200 bg-white px-4 py-3">
                <p className="font-bold">{a.title}</p>
                <p className="text-sm text-ink/60">
                  {a.quiz_title} · {a.status}
                  {a.is_overdue && <span className="ml-2 font-bold text-danger">overdue</span>}
                </p>
                <p className="mt-1 text-xs text-ink/50">
                  Due: {formatDue(a.due_at)} · {statusLabel}
                  {a.max_attempts != null ? ` · max ${a.max_attempts} attempts` : ""}
                </p>
                {live?.active && live.pin && (
                  <p className="mt-2 text-sm font-bold text-brand-dark">
                    Live now — PIN{" "}
                    <span className="font-mono tracking-wider">{live.pin}</span>
                    {" · "}
                    <Link to={`/play?pin=${live.pin}`} className="underline">
                      Join
                    </Link>
                  </p>
                )}
              </li>
            );
          })}
          {!visible.length && (
            <li className="text-ink/50">No assignments yet</li>
          )}
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-2xl">My scores</h2>
        <ul className="mt-3 space-y-2">
          {scores.map((s, i) => (
            <li key={i} className="rounded-xl border border-sky-200 bg-white px-4 py-3">
              <p className="font-bold">{String(s.quiz_title || "Game")}</p>
              <p className="text-sm text-ink/60">
                Score {String(s.score)} · Rank #{String(s.rank)}
              </p>
            </li>
          ))}
          {!scores.length && <li className="text-ink/50">No games played yet</li>}
        </ul>
      </section>
    </div>
  );
}
