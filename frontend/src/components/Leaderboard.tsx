import type { LeaderboardEntry } from "../shared";

interface Props {
  entries: LeaderboardEntry[];
  large?: boolean;
  highlightSid?: string | null;
}

export default function Leaderboard({ entries, large, highlightSid }: Props) {
  return (
    <ol className="mx-auto max-w-xl space-y-2">
      {entries.map((e) => {
        const highlight = highlightSid && e.sid === highlightSid;
        return (
          <li
            key={e.sid}
            className={`flex items-center gap-3 rounded-2xl px-4 py-3 ${
              highlight ? "bg-amber-100 ring-2 ring-accent" : "bg-white border border-sky-100"
            } ${large ? "py-4" : ""}`}
          >
            <span
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-display text-lg font-bold ${
                e.rank === 1
                  ? "bg-amber-400 text-ink"
                  : e.rank === 2
                    ? "bg-slate-300 text-ink"
                    : e.rank === 3
                      ? "bg-orange-300 text-ink"
                      : "bg-sky-100 text-ink"
              }`}
            >
              {e.rank}
            </span>
            <span className={`min-w-0 flex-1 truncate font-extrabold ${large ? "text-xl" : ""}`}>
              {e.nickname}
            </span>
            <span className={`font-display ${large ? "text-2xl" : "text-lg"}`}>{e.score}</span>
          </li>
        );
      })}
      {!entries.length && (
        <li className="rounded-2xl bg-white/70 px-4 py-8 text-center text-ink/50">No scores yet</li>
      )}
    </ol>
  );
}
