import { Navigate, Route, Routes } from "react-router-dom";
import { NavLinks, StudentGate, TeacherGate } from "./components/AuthGates";
import HomePage from "./pages/HomePage";
import HostDashboard from "./pages/HostDashboard";
import QuizEditor from "./pages/QuizEditor";
import HostGame from "./pages/HostGame";
import PlayPage from "./pages/PlayPage";
import HistoryPage from "./pages/HistoryPage";
import TeacherLoginPage from "./pages/TeacherLoginPage";
import TeacherRegisterPage from "./pages/TeacherRegisterPage";
import StudentLoginPage from "./pages/StudentLoginPage";
import StudentDashboard from "./pages/StudentDashboard";
import AttemptPage from "./pages/AttemptPage";
import ClassesPage from "./pages/ClassesPage";
import ClassDetailPage from "./pages/ClassDetailPage";
import AssignmentsPage from "./pages/AssignmentsPage";
import { Link } from "react-router-dom";

function LangToggle() {
  const toggle = () => {
    try {
      const cur = localStorage.getItem("lanquiz_lang") === "vi" ? "en" : "vi";
      localStorage.setItem("lanquiz_lang", cur);
    } catch {
      /* ignore */
    }
    window.location.reload();
  };
  let label = "VI";
  try {
    label = localStorage.getItem("lanquiz_lang") === "vi" ? "EN" : "VI";
  } catch {
    /* ignore */
  }
  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-lg bg-sky-100 px-2 py-1 text-xs font-extrabold"
      aria-label="Toggle language"
    >
      {label}
    </button>
  );
}

export default function App() {
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-sky-200/70 bg-white/75 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="font-display text-2xl tracking-tight text-brand-dark">
            Lan<span className="text-accent">Quiz</span>
          </Link>
          <div className="flex items-center gap-3">
            <NavLinks />
            <LangToggle />
          </div>
        </div>
      </header>
      <main id="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<TeacherLoginPage />} />
          <Route path="/register" element={<TeacherRegisterPage />} />
          <Route path="/student/login" element={<StudentLoginPage />} />
          <Route path="/play" element={<PlayPage />} />

          <Route element={<TeacherGate />}>
            <Route path="/host" element={<HostDashboard />} />
            <Route path="/host/quizzes/new" element={<QuizEditor />} />
            <Route path="/host/quizzes/:id" element={<QuizEditor />} />
            <Route path="/host/game/assignment/:assignmentId" element={<HostGame />} />
            <Route path="/host/game/:quizId" element={<HostGame />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/teacher/classes" element={<ClassesPage />} />
            <Route path="/teacher/classes/:id" element={<ClassDetailPage />} />
            <Route path="/teacher/assignments" element={<AssignmentsPage />} />
          </Route>

          <Route element={<StudentGate />}>
            <Route path="/student" element={<StudentDashboard />} />
            <Route path="/student/attempt/:attemptId" element={<AttemptPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
