import { useEffect, useState } from "react";

interface Props {
  seconds: number;
  active?: boolean;
}

export default function TimerBar({ seconds, active = true }: Props) {
  const [left, setLeft] = useState(seconds);

  useEffect(() => {
    setLeft(seconds);
    if (!active) return;
    const started = Date.now();
    const id = window.setInterval(() => {
      const elapsed = (Date.now() - started) / 1000;
      const remaining = Math.max(0, seconds - elapsed);
      setLeft(remaining);
      if (remaining <= 0) window.clearInterval(id);
    }, 100);
    return () => window.clearInterval(id);
  }, [seconds, active]);

  const pct = Math.max(0, Math.min(100, (left / seconds) * 100));
  const urgent = left <= 5;

  return (
    <div className="w-full">
      <div className="mb-1 flex justify-between text-sm font-extrabold">
        <span>Time</span>
        <span className={urgent ? "text-danger" : ""}>{Math.ceil(left)}s</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-sky-100">
        <div
          className={`h-full rounded-full transition-[width] duration-100 ease-linear ${
            urgent ? "bg-danger" : "bg-brand"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
