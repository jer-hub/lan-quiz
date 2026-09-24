import { Navigate, Link, Outlet } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function TeacherGate() {
  const { ready, isTeacher } = useAuth();
  if (!ready) return <p className="p-8 text-center text-ink/60">Loading…</p>;
  if (!isTeacher) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function StudentGate() {
  const { ready, isStudent } = useAuth();
  if (!ready) return <p className="p-8 text-center text-ink/60">Loading…</p>;
  if (!isStudent) return <Navigate to="/student/login" replace />;
  return <Outlet />;
}

export function AuthBanner() {
  const { ready, isTeacher, isStudent, username, displayName, logout } = useAuth();
  if (!ready || (!isTeacher && !isStudent)) return null;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="hidden text-ink/70 sm:inline">
        {isTeacher ? username : displayName}
      </span>
      <button
        type="button"
        onClick={logout}
        className="rounded-lg px-2 py-1 font-semibold text-ink/70 hover:bg-sky-100"
      >
        Log out
      </button>
    </div>
  );
}

export function NavLinks() {
  const { isTeacher, isStudent } = useAuth();
  return (
    <nav className="flex items-center gap-1 text-sm font-semibold sm:gap-2">
      {isTeacher ? (
        <>
          <Link className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3" to="/host">
            Quizzes
          </Link>
          <Link
            className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3"
            to="/teacher/classes"
          >
            Classes
          </Link>
          <Link
            className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3"
            to="/teacher/assignments"
          >
            Assignments
          </Link>
          <Link className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3" to="/history">
            History
          </Link>
        </>
      ) : isStudent ? (
        <Link className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3" to="/student">
          My class
        </Link>
      ) : (
        <>
          <Link className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3" to="/login">
            Teacher
          </Link>
          <Link
            className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3"
            to="/student/login"
          >
            Student
          </Link>
        </>
      )}
      <Link className="rounded-lg px-2 py-2 text-ink/80 hover:bg-sky-100 sm:px-3" to="/play">
        Play
      </Link>
      <AuthBanner />
    </nav>
  );
}
