import type { LeaderboardEntry } from "../shared";

interface Props {
  podium: LeaderboardEntry[];
}

const heights = ["h-36", "h-28", "h-20"];
const order = [1, 0, 2]; // visual: 2nd, 1st, 3rd

export default function Podium({ podium }: Props) {
  const byRank = [1, 2, 3].map((rank) => podium.find((p) => p.rank === rank));

  return (
    <div className="animate-pop flex items-end justify-center gap-3 sm:gap-6">
      {order.map((idx) => {
        const entry = byRank[idx];
        const place = idx + 1;
        if (!entry) {
          return <div key={place} className="w-24 sm:w-32" />;
        }
        return (
          <div key={entry.sid} className="flex w-24 flex-col items-center sm:w-32">
            <p className="mb-2 truncate text-center font-extrabold">{entry.nickname}</p>
            <p className="mb-2 font-display text-xl text-brand-dark">{entry.score}</p>
            <div
              className={`flex w-full items-start justify-center rounded-t-2xl pt-3 font-display text-3xl text-white ${heights[idx]} ${
                place === 1 ? "bg-amber-400" : place === 2 ? "bg-slate-400" : "bg-orange-400"
              }`}
            >
              {place}
            </div>
          </div>
        );
      })}
    </div>
  );
}
