import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function StudentLoginPage() {
  const { isStudent, loginStudent, ready } = useAuth();
  const navigate = useNavigate();
  const [studentCode, setStudentCode] = useState("");
  const [password, setPassword] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (ready && isStudent) return <Navigate to="/student" replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await loginStudent(studentCode, password, joinCode || undefined);
      navigate("/student");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <form
        onSubmit={(e) => void submit(e)}
        className="rounded-3xl border border-sky-200 bg-white p-6 shadow-sm"
      >
        <h1 className="font-display text-3xl">Student login</h1>
        <p className="mt-1 text-sm text-ink/70">
          Use the student code your teacher gave you. Default password is the same as your code.
        </p>
        {error && (
          <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </p>
        )}
        <label className="mt-4 block text-sm font-bold">
          Student code
          <input
            className="mt-1 w-full rounded-xl border border-sky-200 px-3 py-2.5 uppercase"
            value={studentCode}
            onChange={(e) => setStudentCode(e.target.value.toUpperCase())}
            required
          />
        </label>
        <label className="mt-3 block text-sm font-bold">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded-xl border border-sky-200 px-3 py-2.5"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <label className="mt-3 block text-sm font-bold">
          Class join code <span className="font-normal text-ink/50">(if needed)</span>
          <input
            className="mt-1 w-full rounded-xl border border-sky-200 px-3 py-2.5 uppercase"
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-2xl bg-brand py-3 font-extrabold text-white disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="mt-4 text-center text-sm">
          <Link to="/play" className="font-bold text-brand-dark underline">
            Or join a live game with PIN
          </Link>
        </p>
      </form>
    </div>
  );
}
