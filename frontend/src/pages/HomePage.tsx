import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useLang } from "../i18n";

export default function HomePage() {
  const { isTeacher, isStudent } = useAuth();
  const { t } = useLang();

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
            {t.heroTitle}
          </h1>
          <p className="mt-3 max-w-lg text-base text-sky-50 sm:text-lg">
            {t.heroSub}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {isTeacher ? (
              <Link
                to="/host"
                className="rounded-2xl bg-accent px-6 py-3 text-lg font-extrabold text-ink shadow-lg transition hover:brightness-110"
              >
                {t.teacherDashboard}
              </Link>
            ) : isStudent ? (
              <Link
                to="/student"
                className="rounded-2xl bg-accent px-6 py-3 text-lg font-extrabold text-ink shadow-lg transition hover:brightness-110"
              >
                {t.myClass}
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="rounded-2xl bg-accent px-6 py-3 text-lg font-extrabold text-ink shadow-lg transition hover:brightness-110"
                >
                  {t.teacherLogin}
                </Link>
                <Link
                  to="/student/login"
                  className="rounded-2xl bg-white/20 px-6 py-3 text-lg font-bold backdrop-blur transition hover:bg-white/30"
                >
                  {t.studentLogin}
                </Link>
              </>
            )}
            <Link
              to="/play"
              className="rounded-2xl bg-white/20 px-6 py-3 text-lg font-bold backdrop-blur transition hover:bg-white/30"
            >
              {t.joinPin}
            </Link>
          </div>
        </div>
      </section>
      <section className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-3xl border border-sky-200 bg-white p-6 shadow-sm">
          <h2 className="font-display text-2xl">Host on this PC</h2>
          <p className="mt-2 text-ink/70">
            Teachers create the game here and show the PIN/QR. Allow TCP 8000 through the
            firewall when Windows asks.
          </p>
        </div>
        <div className="rounded-3xl border border-sky-200 bg-white p-6 shadow-sm">
          <h2 className="font-display text-2xl">Join via phone</h2>
          <p className="mt-2 text-ink/70">
            Same Wi-Fi + scan QR (or open /play with the PIN). If QR shows localhost, the
            host must set HOST_IP to its LAN IP and restart.
          </p>
        </div>
      </section>
    </div>
  );
}
