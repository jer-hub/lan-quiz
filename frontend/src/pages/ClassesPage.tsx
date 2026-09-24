import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ClassOut } from "../shared";

export default function ClassesPage() {
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setClasses(await api.listClasses());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createClass({ name });
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="font-display text-4xl">Classes</h1>
      <p className="mt-1 text-ink/70">Create a class, add a roster, then assign quizzes.</p>
      {error && <p className="mt-3 text-danger">{error}</p>}

      <form onSubmit={(e) => void create(e)} className="mt-6 flex flex-wrap gap-2">
        <input
          className="min-w-[200px] flex-1 rounded-xl border border-sky-200 px-3 py-2.5"
          placeholder="Class name (e.g. Period 3 Science)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <button type="submit" className="rounded-xl bg-brand px-4 py-2.5 font-extrabold text-white">
          Create class
        </button>
      </form>

      <ul className="mt-8 space-y-3">
        {classes.map((c) => (
          <li key={c.id} className="rounded-2xl border border-sky-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="font-display text-2xl">{c.name}</h2>
                <p className="text-sm text-ink/60">
                  Join code <span className="font-mono font-bold tracking-wider">{c.join_code}</span> ·{" "}
                  {c.student_count} students
                </p>
              </div>
              <Link
                to={`/teacher/classes/${c.id}`}
                className="rounded-xl bg-sky-100 px-4 py-2 font-bold hover:bg-sky-200"
              >
                Manage
              </Link>
            </div>
          </li>
        ))}
        {!classes.length && (
          <li className="rounded-2xl border-2 border-dashed border-sky-200 px-4 py-10 text-center text-ink/50">
            No classes yet
          </li>
        )}
      </ul>
    </div>
  );
}
