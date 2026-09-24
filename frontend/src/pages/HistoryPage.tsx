import { useEffect, useState } from "react";
import { api } from "../api";
import type { GameHistory } from "../shared";

export default function HistoryPage() {
  const [rows, setRows] = useState<GameHistory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

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
                  onClick={() => setOpenId(openId === row.id ? null : row.id)}
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
                  className="rounded-lg bg-red-50 px-3 py-1.5 text-sm font-bold text-danger"
                  onClick={() => void onDelete(row.id)}
                >
                  Delete
                </button>
              </div>
            </div>
            {openId === row.id && (
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
