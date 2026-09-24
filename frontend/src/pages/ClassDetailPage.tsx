import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { ClassOut, Gradebook, StudentOut } from "../shared";

export default function ClassDetailPage() {
  const { id } = useParams();
  const classId = Number(id);
  const fileRef = useRef<HTMLInputElement>(null);

  const [classroom, setClassroom] = useState<ClassOut | null>(null);
  const [students, setStudents] = useState<StudentOut[]>([]);
  const [gradebook, setGradebook] = useState<Gradebook | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [studentCode, setStudentCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setClassroom(await api.getClass(classId));
      setStudents(await api.listStudents(classId));
      setGradebook(await api.getGradebook(classId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  };

  useEffect(() => {
    if (classId) void load();
  }, [classId]);

  const addStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.addStudent(classId, {
        display_name: displayName,
        student_code: studentCode,
      });
      setDisplayName("");
      setStudentCode("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add failed");
    }
  };

  const removeStudent = async (studentId: number) => {
    if (!confirm("Remove this student from the roster?")) return;
    await api.deleteStudent(classId, studentId);
    await load();
  };

  const onImport = async (file: File) => {
    try {
      await api.importRoster(classId, file);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    }
  };

  const exportCsv = async () => {
    const blob = await api.exportGradebook(classId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gradebook-class-${classId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!classroom) {
    return <p className="p-8 text-ink/60">{error || "Loading…"}</p>;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <Link to="/teacher/classes" className="text-sm font-bold text-brand-dark hover:underline">
        ← Classes
      </Link>
      <h1 className="mt-2 font-display text-4xl">{classroom.name}</h1>
      <p className="mt-1 text-ink/70">
        Class join code:{" "}
        <span className="font-mono text-xl font-bold tracking-wider">{classroom.join_code}</span>
      </p>
      {error && <p className="mt-3 text-danger">{error}</p>}

      <section className="mt-8">
        <h2 className="font-display text-2xl">Roster</h2>
        <form onSubmit={(e) => void addStudent(e)} className="mt-3 flex flex-wrap gap-2">
          <input
            className="rounded-xl border border-sky-200 px-3 py-2"
            placeholder="Display name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
          <input
            className="rounded-xl border border-sky-200 px-3 py-2 uppercase"
            placeholder="Student code"
            value={studentCode}
            onChange={(e) => setStudentCode(e.target.value.toUpperCase())}
            required
          />
          <button type="submit" className="rounded-xl bg-brand px-4 py-2 font-bold text-white">
            Add
          </button>
          <button
            type="button"
            className="rounded-xl border border-sky-300 bg-white px-4 py-2 font-bold"
            onClick={() => fileRef.current?.click()}
          >
            Import CSV
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onImport(f);
              e.target.value = "";
            }}
          />
        </form>
        <p className="mt-2 text-xs text-ink/50">
          CSV headers: display_name,student_code[,password] — default password = student_code
        </p>
        <ul className="mt-4 divide-y divide-sky-100 rounded-2xl border border-sky-200 bg-white">
          {students.map((s) => (
            <li key={s.id} className="flex items-center justify-between px-4 py-3">
              <span>
                <span className="font-bold">{s.display_name}</span>{" "}
                <span className="font-mono text-sm text-ink/60">{s.student_code}</span>
              </span>
              <button
                type="button"
                className="text-sm font-bold text-danger"
                onClick={() => void removeStudent(s.id)}
              >
                Remove
              </button>
            </li>
          ))}
          {!students.length && (
            <li className="px-4 py-8 text-center text-ink/50">No students yet</li>
          )}
        </ul>
      </section>

      <section className="mt-10">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-2xl">Gradebook</h2>
          <button
            type="button"
            onClick={() => void exportCsv()}
            className="rounded-xl bg-accent px-4 py-2 font-extrabold text-ink"
          >
            Export CSV
          </button>
        </div>
        {gradebook && gradebook.assignments.length > 0 ? (
          <div className="overflow-x-auto rounded-2xl border border-sky-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-sky-50">
                <tr>
                  <th className="px-3 py-2 font-bold">Student</th>
                  {gradebook.assignments.map((a) => (
                    <th key={a.id} className="px-3 py-2 font-bold">
                      {a.title}
                    </th>
                  ))}
                  <th className="px-3 py-2 font-bold">Total</th>
                </tr>
              </thead>
              <tbody>
                {gradebook.rows.map((row) => (
                  <tr key={row.student_id} className="border-t border-sky-100">
                    <td className="px-3 py-2 font-semibold">
                      {row.display_name}{" "}
                      <span className="font-mono text-xs text-ink/50">{row.student_code}</span>
                    </td>
                    {row.scores.map((cell) => (
                      <td key={cell.assignment_id} className="px-3 py-2">
                        {cell.score == null ? "—" : cell.score}
                      </td>
                    ))}
                    <td className="px-3 py-2 font-bold">{row.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-ink/50">No assignment scores yet. Create an assignment and host a game.</p>
        )}
      </section>
    </div>
  );
}
