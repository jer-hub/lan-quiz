import { useEffect, useState } from "react";
import { api } from "../api";
import type { GameHistory, QuestionAnalysis } from "../shared";

export default function HistoryPage() {
  const [rows, setRows] = useState<GameHistory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<Record<number, QuestionAnalysis[]>>({});

  const load = async () => {
    try {
      setRows(await api.listHistory());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load history");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onDelete = async (id: number) => {
    if (!confirm("Delete this history entry?")) return;
    await api.deleteHistory(id);
    await load();
  };

  const toggle = async (id: number) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    if (!analysis[id]) {
      try {
        const res = await api.historyAnalysis(id);
        setAnalysis((p) => ({ ...p, [id]: res.analysis }));
      } catch {
        /* leaderboard still shows */
      }
    }
  };

  const downloadAnalysis = (row: GameHistory) => {
    const a = analysis[row.id] || [];
    const lines = ["question_index,text,pct_correct,correct,total"];
    for (const q of a) {
      const text = `"${(q.text || "").replace(/"/g, '""')}"`;
      lines.push(`${q.question_index},${text},${q.pct_correct},${q.correct},${q.total}`);
    }
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const el = document.createElement("a");
    el.href = url;
    el.download = `analysis-${row.pin}-${row.id}.csv`;
    el.click();
    URL.revokeObjectURL(url);
  };

  const onExport = (row: GameHistory) => {
    const blob = new Blob([JSON.stringify(row, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lanquiz-${row.pin}-${row.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="font-display text-4xl">Game history</h1>
      <p className="mt-1 text-ink/70">Finished sessions saved on this server.</p>
      {error && <p className="mt-4 text-danger">{error}</p>}
      <ul className="mt-6 space-y-3">
        {rows.map((row) => (
          <li key={row.id} className="rounded-2xl border border-sky-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="font-display text-xl">{row.quiz_title}</h2>
                <p className="text-sm text-ink/60">
                  PIN {row.pin} · {row.player_count} players ·{" "}
                  {new Date(row.played_at).toLocaleString()}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="rounded-lg bg-sky-100 px-3 py-1.5 text-sm font-bold"
                  onClick={() => void toggle(row.id)}
                >
                  {openId === row.id ? "Hide" : "Results"}
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-sky-100 px-3 py-1.5 text-sm font-bold"
                  onClick={() => onExport(row)}
                >
                  Export
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-sky-100 px-3 py-1.5 text-sm font-bold"
                  onClick={() => downloadAnalysis(row)}
                >
                  Analysis CSV
                </button>
                <button
                  type="button"
                  className="rounded-lg bg-red-50 px-3 py-1.5 text-sm font-bold text-danger"
                  onClick={() => void onDelete(row.id)}
                >
                  Delete
                </button>
              </div>
            </div>
            {openId === row.id && (
              <>
                <ol className="mt-4 space-y-1 border-t border-sky-100 pt-3">
                  {row.results.map((r) => (
                    <li key={r.sid} className="flex justify-between text-sm font-semibold">
                      <span>
                        #{r.rank} {r.nickname}
                      </span>
                      <span>{r.score}</span>
                    </li>
                  ))}
                </ol>
                {(analysis[row.id] || []).length > 0 && (
                  <div className="mt-4 overflow-x-auto rounded-xl border border-sky-100">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-sky-50">
                        <tr>
                          <th className="px-3 py-2">Q#</th>
                          <th className="px-3 py-2">Question</th>
                          <th className="px-3 py-2">% correct</th>
                          <th className="px-3 py-2">Answers</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analysis[row.id].map((q) => (
                          <tr key={q.question_index} className="border-t border-sky-100">
                            <td className="px-3 py-2 font-bold">Q{q.question_index + 1}</td>
                            <td className="max-w-[240px] truncate px-3 py-2">{q.text}</td>
                            <td className="px-3 py-2 font-bold">{q.pct_correct}%</td>
                            <td className="px-3 py-2 text-ink/60">
                              {q.correct}/{q.total}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </li>
        ))}
        {!rows.length && !error && (
          <li className="rounded-2xl border-2 border-dashed border-sky-200 px-4 py-12 text-center text-ink/50">
            No games played yet
          </li>
        )}
      </ul>
    </div>
  );
}
