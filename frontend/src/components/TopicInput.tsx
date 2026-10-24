import { useState } from "react";
import { TOPIC_MAX_LENGTH } from "../shared";

/** Same rules as the server (app/topics.py): trim, collapse spaces, compare case-insensitively. */
export function normalizeTopic(name: string): string {
  return name.split(/\s+/).filter(Boolean).join(" ");
}

function sameTopic(a: string, b: string): boolean {
  return normalizeTopic(a).toLowerCase() === normalizeTopic(b).toLowerCase();
}

interface Props {
  id: string;
  topics: string[];
  suggestions: string[];
  onChange: (topics: string[]) => void;
}

/** Topic chips for one question, with suggestions from the teacher's existing topics. */
export default function TopicInput({ id, topics, suggestions, onChange }: Props) {
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const name = normalizeTopic(raw);
    setDraft("");
    if (!name || topics.some((t) => sameTopic(t, name))) return;
    // Reuse the teacher's existing spelling so the chip matches what the server stores.
    const existing = suggestions.find((s) => sameTopic(s, name));
    onChange([...topics, existing ?? name]);
  };

  const listId = `${id}-suggestions`;
  const available = suggestions.filter((s) => !topics.some((t) => sameTopic(t, s)));

  return (
    <div className="mb-3">
      <label htmlFor={id} className="mb-1 block text-sm font-bold">
        Topics
      </label>
      <div className="flex flex-wrap items-center gap-2">
        {topics.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-3 py-1 text-sm font-semibold"
          >
            {t}
            <button
              type="button"
              aria-label={`Remove topic ${t}`}
              className="font-bold text-ink/50 hover:text-danger"
              onClick={() => onChange(topics.filter((x) => x !== t))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          id={id}
          list={listId}
          maxLength={TOPIC_MAX_LENGTH}
          className="min-w-[10rem] flex-1 rounded-xl border border-sky-200 px-3 py-1.5"
          value={draft}
          placeholder={topics.length ? "Add another topic" : "e.g. Fractions"}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add(draft);
            } else if (e.key === "Backspace" && !draft && topics.length) {
              onChange(topics.slice(0, -1));
            }
          }}
          onBlur={() => add(draft)}
        />
        <datalist id={listId}>
          {available.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </div>
    </div>
  );
}
