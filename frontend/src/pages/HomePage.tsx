import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function HomePage() {
  const { isTeacher, isStudent } = useAuth();

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-6xl flex-col justify-center px-4 py-10">
      <section className="animate-slide-up relative overflow-hidden rounded-3xl bg-gradient-to-br from-sky-500 via-cyan-500 to-teal-500 px-6 py-14 text-white shadow-xl sm:px-12 sm:py-20">
        <div
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 30%, #fff6 0 12%, transparent 13%), radial-gradient(circle at 80% 20%, #fbbf2466 0 18%, transparent 19%), radial-gradient(circle at 70% 80%, #fff4 0 10%, transparent 11%)",
          }}
        />
        <div className="relative max-w-2xl">
          <p className="font-display text-5xl leading-none tracking-tight sm:text-7xl">
            LanQuiz
          </p>
          <h1 className="mt-4 font-display text-2xl leading-tight sm:text-3xl">
            Classroom quizzes on your own Wi‑Fi
          </h1>
          <p className="mt-3 max-w-lg text-base text-sky-50 sm:text-lg">
            Teachers manage classes and assignments. Students join with a roster code.
            Live PIN games work fully offline after setup.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {isTeacher ? (
              <Link
                to="/host"
                className="rounded-2xl bg-accent px-6 py-3 text-lg font-extrabold text-ink shadow-lg transition hover:brightness-110"
              >
                Teacher dashboard
              </Link>
            ) : isStudent ? (
              <Link
                to="/student"
                className="rounded-2xl bg-accent px-6 py-3 text-lg font-extrabold text-ink shadow-lg transition hover:brightness-110"
              >
                My class
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="rounded-2xl bg-accent px-6 py-3 text-lg font-extrabold text-ink shadow-lg transition hover:brightness-110"
                >
                  Teacher login
                </Link>
                <Link
                  to="/student/login"
                  className="rounded-2xl bg-white/20 px-6 py-3 text-lg font-bold backdrop-blur transition hover:bg-white/30"
                >
                  Student login
                </Link>
              </>
            )}
            <Link
              to="/play"
              className="rounded-2xl bg-white/20 px-6 py-3 text-lg font-bold backdrop-blur transition hover:bg-white/30"
            >
              Join with PIN
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
