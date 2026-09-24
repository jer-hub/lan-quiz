import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useSocket, useSocketEvent } from "../hooks/useSocket";
import { useAuth } from "../hooks/useAuth";
import type {
  GameEndedPayload,
  LeaderboardEntry,
  LobbyState,
  QuestionEndedPayload,
  QuestionPayload,
} from "../shared";
import TimerBar from "../components/TimerBar";
import Leaderboard from "../components/Leaderboard";
import Podium from "../components/Podium";

type Phase = "connecting" | "lobby" | "question" | "reveal" | "finished" | "error";

export default function HostGame() {
  const { quizId, assignmentId } = useParams();
  const { socket, connected } = useSocket();
  const { token } = useAuth();
  const createdRef = useRef(false);

  const [phase, setPhase] = useState<Phase>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [pin, setPin] = useState("");
  const [qr, setQr] = useState("");
  const [joinUrl, setJoinUrl] = useState("");
  const [quizTitle, setQuizTitle] = useState("");
  const [lobby, setLobby] = useState<LobbyState | null>(null);
  const [question, setQuestion] = useState<QuestionPayload | null>(null);
  const [reveal, setReveal] = useState<QuestionEndedPayload | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [answerCount, setAnswerCount] = useState(0);
  const [final, setFinal] = useState<GameEndedPayload | null>(null);

  useEffect(() => {
    if (!connected || createdRef.current || !token) return;
    if (!quizId && !assignmentId) return;
    createdRef.current = true;
    if (assignmentId) {
      socket.emit("create_game", { assignment_id: Number(assignmentId), token });
    } else {
      socket.emit("create_game", { quiz_id: Number(quizId), token });
    }
  }, [connected, quizId, assignmentId, socket, token]);

  // Surface a stuck-connecting state if the socket never comes up
  useEffect(() => {
    if (phase !== "connecting") return;
    const t = window.setTimeout(() => {
      if (!connected) {
        setError(
          "Could not connect to the live game server. Check that LanQuiz is running and refresh the page.",
        );
        setPhase("error");
      }
    }, 8000);
    return () => window.clearTimeout(t);
  }, [phase, connected]);

  useSocketEvent("error", (data: { message: string }) => {
    setError(data.message);
    setPhase("error");
  });

  useSocketEvent(
    "game_created",
    (data: LobbyState & { qr: string; join_url: string; quiz_title: string }) => {
      setPin(data.pin);
      setQr(data.qr);
      setJoinUrl(data.join_url);
      setQuizTitle(data.quiz_title);
      setLobby(data);
      setPhase("lobby");
    },
  );

  useSocketEvent("lobby_update", (data: LobbyState) => {
    setLobby(data);
  });

  useSocketEvent("game_started", () => {
    setPhase("question");
  });

  useSocketEvent("question_started", (data: QuestionPayload) => {
    setQuestion(data);
    setReveal(null);
    setAnswerCount(0);
    setPhase("question");
  });

  useSocketEvent("answer_received", (data: { answer_count: number }) => {
    setAnswerCount(data.answer_count);
  });

  useSocketEvent("question_ended", (data: QuestionEndedPayload) => {
    setReveal(data);
    setLeaderboard(data.leaderboard);
    setPhase("reveal");
  });

  useSocketEvent(
    "leaderboard_update",
    (data: { leaderboard: LeaderboardEntry[] }) => {
      setLeaderboard(data.leaderboard);
    },
  );

  useSocketEvent("game_ended", (data: GameEndedPayload) => {
    setFinal(data);
    setLeaderboard(data.leaderboard);
    setPhase("finished");
  });

  const start = useCallback(() => socket.emit("start_game"), [socket]);
  const next = useCallback(() => socket.emit("next_question"), [socket]);
  const skip = useCallback(() => socket.emit("skip_question"), [socket]);
  const end = useCallback(() => {
    if (confirm("End the game now?")) socket.emit("end_game");
  }, [socket]);
  const kick = useCallback(
    (sid: string) => socket.emit("kick_player", { sid }),
    [socket],
  );

  if (phase === "error") {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <p className="font-display text-3xl text-danger">Something went wrong</p>
        <p className="mt-2">{error}</p>
        <Link to="/host" className="mt-6 inline-block font-bold text-brand-dark underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (phase === "finished" && final) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <h1 className="text-center font-display text-4xl sm:text-5xl">Final results</h1>
        <p className="mt-2 text-center text-lg text-ink/70">{final.quiz_title}</p>
        <div className="mt-8">
          <Podium podium={final.podium} />
        </div>
        <div className="mt-10">
          <Leaderboard entries={final.leaderboard} large />
        </div>
        <div className="mt-8 text-center">
          <Link
            to="/host"
            className="inline-block rounded-xl bg-brand px-6 py-3 font-extrabold text-white"
          >
            Back to host
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-[calc(100dvh-4rem)] max-w-6xl px-4 py-6">
      {/* Lobby */}
      {phase === "lobby" && (
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-3xl bg-gradient-to-br from-sky-600 to-cyan-500 p-8 text-white shadow-xl">
            <p className="text-lg font-semibold text-sky-100">Join at</p>
            <p className="mt-1 break-all font-mono text-xl sm:text-2xl">{joinUrl || "…"}</p>
            <p className="mt-8 text-sky-100">Game PIN</p>
            <p className="font-display text-6xl tracking-[0.2em] sm:text-8xl">{pin}</p>
            <p className="mt-4 text-xl font-semibold">{quizTitle}</p>
            <p className="mt-1 text-sky-100">
              {lobby?.player_count ?? 0} player{(lobby?.player_count ?? 0) === 1 ? "" : "s"} waiting
              {lobby?.requires_student_code ? " · roster codes required" : ""}
            </p>
            <button
              type="button"
              disabled={!lobby?.player_count}
              onClick={start}
              className="mt-8 rounded-2xl bg-accent px-8 py-4 text-xl font-extrabold text-ink shadow-lg transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Start game
            </button>
          </div>
          <div className="flex flex-col items-center rounded-3xl border border-sky-200 bg-white p-6 shadow-sm">
            {qr ? (
              <img src={qr} alt="Join QR code" className="h-56 w-56 rounded-xl bg-white p-2" />
            ) : (
              <div className="flex h-56 w-56 items-center justify-center rounded-xl bg-sky-50">
                Generating QR…
              </div>
            )}
            <p className="mt-4 text-center text-sm text-ink/60">Scan to open the join page with PIN</p>
            <ul className="mt-6 w-full space-y-2">
              {(lobby?.players || []).map((p) => (
                <li
                  key={p.sid}
                  className="flex items-center justify-between rounded-xl bg-sky-50 px-3 py-2"
                >
                  <span className="font-bold">{p.nickname}</span>
                  <button
                    type="button"
                    onClick={() => kick(p.sid)}
                    className="text-sm font-bold text-danger"
                  >
                    Kick
                  </button>
                </li>
              ))}
              {!lobby?.players?.length && (
                <li className="animate-pulse-soft py-6 text-center text-ink/50">
                  Waiting for players…
                </li>
              )}
            </ul>
          </div>
        </div>
      )}

      {/* Question / reveal / leaderboard */}
      {(phase === "question" || phase === "reveal") && question && (
        <div className="animate-slide-up">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold uppercase tracking-wide text-brand-dark">
                Question {question.question_index + 1} / {question.total_questions}
              </p>
              <p className="text-sm text-ink/60">
                Answers: {answerCount} / {lobby?.player_count ?? "—"} · PIN {pin}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {phase === "question" && (
                <button
                  type="button"
                  onClick={next}
                  className="rounded-xl bg-sky-100 px-4 py-2 font-bold"
                >
                  Force reveal
                </button>
              )}
              {phase === "reveal" && (
                <button
                  type="button"
                  onClick={next}
                  className="rounded-xl bg-brand px-4 py-2 font-extrabold text-white"
                >
                  {question.question_index + 1 >= question.total_questions
                    ? "Show podium"
                    : "Next question"}
                </button>
              )}
              <button type="button" onClick={skip} className="rounded-xl bg-sky-100 px-4 py-2 font-bold">
                Skip
              </button>
              <button type="button" onClick={end} className="rounded-xl bg-red-50 px-4 py-2 font-bold text-danger">
                End game
              </button>
            </div>
          </div>

          {phase === "question" && (
            <>
              <TimerBar seconds={question.time_limit} active key={question.question_index} />
              <h2 className="mt-6 text-center font-display text-3xl leading-tight sm:text-5xl">
                {question.text}
              </h2>
              {question.image && (
                <img
                  src={question.image}
                  alt=""
                  className="mx-auto mt-6 max-h-56 rounded-2xl object-contain"
                />
              )}
              <div className="mt-8 grid gap-3 sm:grid-cols-2">
                {question.options.map((opt, i) => (
                  <div
                    key={i}
                    className="rounded-2xl px-5 py-6 text-center text-xl font-extrabold text-white shadow-md"
                    style={{
                      backgroundColor: ["#e11d48", "#2563eb", "#ca8a04", "#059669", "#7c3aed", "#ea580c"][i],
                    }}
                  >
                    {opt}
                  </div>
                ))}
              </div>
            </>
          )}

          {phase === "reveal" && reveal && (
            <div>
              <h2 className="text-center font-display text-3xl sm:text-4xl">Answer reveal</h2>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                {reveal.options.map((opt, i) => {
                  const correct = reveal.correct_indices.includes(i);
                  return (
                    <div
                      key={i}
                      className={`rounded-2xl px-5 py-5 text-center text-lg font-extrabold text-white ${
                        correct ? "ring-4 ring-white ring-offset-2 ring-offset-success" : "opacity-60"
                      }`}
                      style={{
                        backgroundColor: ["#e11d48", "#2563eb", "#ca8a04", "#059669", "#7c3aed", "#ea580c"][i],
                      }}
                    >
                      {opt}
                      {correct && <span className="mt-1 block text-sm">Correct</span>}
                    </div>
                  );
                })}
              </div>
              <h3 className="mb-4 mt-10 text-center font-display text-3xl">Leaderboard</h3>
              <Leaderboard entries={leaderboard.length ? leaderboard : reveal.leaderboard} large />
            </div>
          )}
        </div>
      )}

      {phase === "connecting" && (
        <p className="py-20 text-center text-lg text-ink/60">Creating game session…</p>
      )}
    </div>
  );
}
