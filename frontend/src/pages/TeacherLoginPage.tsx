import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function TeacherLoginPage() {
  const { isTeacher, loginTeacher, ready } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (ready && isTeacher) return <Navigate to="/host" replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await loginTeacher(username, password);
      navigate("/host");
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
        <h1 className="font-display text-3xl">Teacher login</h1>
        <p className="mt-1 text-sm text-ink/70">
          No account? <Link className="font-bold text-brand-dark underline" to="/register">Register</Link>
        </p>
        {error && (
          <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </p>
        )}
        <label className="mt-4 block text-sm font-bold">
          Username
          <input
            className="mt-1 w-full rounded-xl border border-sky-200 px-3 py-2.5"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
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
            autoComplete="current-password"
            required
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-2xl bg-brand py-3 font-extrabold text-white disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
