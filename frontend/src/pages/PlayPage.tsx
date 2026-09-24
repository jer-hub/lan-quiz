import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useSocket, useSocketEvent } from "../hooks/useSocket";
import type {
  GameEndedPayload,
  LeaderboardEntry,
  LobbyState,
  QuestionEndedPayload,
  QuestionPayload,
} from "../shared";
import { OPTION_SHAPES } from "../shared";
import TimerBar from "../components/TimerBar";
import Leaderboard from "../components/Leaderboard";
import Podium from "../components/Podium";

type Phase = "join" | "lobby" | "question" | "waiting" | "reveal" | "leaderboard" | "finished";

const COLORS = ["#e11d48", "#2563eb", "#ca8a04", "#059669", "#7c3aed", "#ea580c"];

export default function PlayPage() {
  const [params] = useSearchParams();
  const { socket, connected } = useSocket();

  const [phase, setPhase] = useState<Phase>("join");
  const [pin, setPin] = useState((params.get("pin") || "").toUpperCase());
  const [nickname, setNickname] = useState("");
  const [studentCode, setStudentCode] = useState("");
  const [requiresCode, setRequiresCode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lobby, setLobby] = useState<LobbyState | null>(null);
  const [mySid, setMySid] = useState<string | null>(null);
  const [question, setQuestion] = useState<QuestionPayload | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [locked, setLocked] = useState(false);
  const [reveal, setReveal] = useState<QuestionEndedPayload | null>(null);
  const [lastPoints, setLastPoints] = useState<number | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [final, setFinal] = useState<GameEndedPayload | null>(null);

  useEffect(() => {
    const p = pin.trim().toUpperCase();
    if (p.length < 4) {
      setRequiresCode(false);
      return;
    }
    const t = window.setTimeout(() => {
      void api
        .peekPin(p)
        .then((info) => setRequiresCode(info.requires_student_code))
        .catch(() => setRequiresCode(false));
    }, 300);
    return () => window.clearTimeout(t);
  }, [pin]);

  useSocketEvent("error", (data: { message: string }) => {
    setError(data.message);
  });

  useSocketEvent("joined", (data: LobbyState & { sid: string; nickname: string }) => {
    setMySid(data.sid);
    setLobby(data);
    setPhase("lobby");
    setError(null);
  });

  useSocketEvent("lobby_update", (data: LobbyState) => {
    setLobby(data);
  });

  useSocketEvent("kicked", (data: { reason: string }) => {
    setError(data.reason || "You were removed from the game");
    setPhase("join");
    setLobby(null);
  });

  useSocketEvent("game_started", () => {
    setPhase("question");
  });

  useSocketEvent("question_started", (data: QuestionPayload) => {
    setQuestion(data);
    setSelected(null);
    setLocked(false);
    setReveal(null);
    setLastPoints(null);
    setPhase("question");
  });

  useSocketEvent("answer_ack", () => {
    setLocked(true);
    setPhase("waiting");
  });

  useSocketEvent("question_ended", (data: QuestionEndedPayload) => {
    setReveal(data);
    setLeaderboard(data.leaderboard);
    if (mySid) {
      const mine = data.results.find((r) => r.sid === mySid);
      setLastPoints(mine?.points ?? 0);
    }
    setPhase("reveal");
  });

  useSocketEvent("leaderboard_update", (data: { leaderboard: LeaderboardEntry[] }) => {
    setLeaderboard(data.leaderboard);
    setPhase("leaderboard");
  });

  useSocketEvent("game_ended", (data: GameEndedPayload) => {
    setFinal(data);
    setLeaderboard(data.leaderboard);
    setPhase("finished");
  });

  const join = useCallback(() => {
    setError(null);
    socket.emit("join_game", {
      pin: pin.trim().toUpperCase(),
      nickname: nickname.trim(),
      student_code: studentCode.trim().toUpperCase() || undefined,
    });
  }, [socket, pin, nickname, studentCode]);

  const canJoin = connected && pin.trim().length >= 4 && (requiresCode ? studentCode.trim().length >= 1 : nickname.trim().length >= 1);

  const submit = useCallback(
    (optionIndex: number) => {
      if (locked || phase !== "question") return;
      setSelected(optionIndex);
      socket.emit("submit_answer", { option_index: optionIndex });
    },
    [locked, phase, socket],
  );

  const myRank = useMemo(() => {
    if (!mySid) return null;
    return leaderboard.find((e) => e.sid === mySid) || null;
  }, [leaderboard, mySid]);

  if (phase === "finished" && final) {
    return (
      <div className="mx-auto max-w-lg px-4 py-10">
        <h1 className="text-center font-display text-4xl">Game over</h1>
        <p className="mt-1 text-center text-ink/70">{final.quiz_title}</p>
        {myRank && (
          <p className="mt-4 text-center font-display text-2xl text-brand-dark">
            You placed #{myRank.rank} · {myRank.score} pts
          </p>
        )}
        <div className="mt-8">
          <Podium podium={final.podium} />
        </div>
        <div className="mt-8">
          <Leaderboard entries={final.leaderboard} highlightSid={mySid} />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-6">
      {phase === "join" && (
        <div className="animate-slide-up rounded-3xl border border-sky-200 bg-white p-6 shadow-sm">
          <h1 className="font-display text-4xl">Join LanQuiz</h1>
          <p className="mt-1 text-ink/70">Enter the PIN shown on the host screen.</p>
          {error && (
            <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              {error}
            </p>
          )}
          <label className="mt-6 block">
            <span className="mb-1 block text-sm font-bold">Game PIN</span>
            <input
              className="w-full rounded-xl border border-sky-200 px-4 py-3 text-center font-display text-3xl tracking-[0.25em] uppercase"
              value={pin}
              onChange={(e) => setPin(e.target.value.toUpperCase())}
              maxLength={6}
              autoComplete="off"
              inputMode="text"
            />
          </label>
          {requiresCode ? (
            <label className="mt-4 block">
              <span className="mb-1 block text-sm font-bold">Student code</span>
              <input
                className="w-full rounded-xl border border-sky-200 px-4 py-3 text-lg font-semibold uppercase"
                value={studentCode}
                onChange={(e) => setStudentCode(e.target.value.toUpperCase())}
                maxLength={40}
                placeholder="From your teacher roster"
              />
              <span className="mt-1 block text-xs text-ink/50">
                Class game — your display name comes from the roster.
              </span>
            </label>
          ) : (
            <label className="mt-4 block">
              <span className="mb-1 block text-sm font-bold">Nickname</span>
              <input
                className="w-full rounded-xl border border-sky-200 px-4 py-3 text-lg font-semibold"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                maxLength={24}
                placeholder="Your name"
              />
            </label>
          )}
          <button
            type="button"
            disabled={!canJoin}
            onClick={join}
            className="mt-6 w-full rounded-2xl bg-brand py-4 text-xl font-extrabold text-white disabled:opacity-50"
          >
            {connected ? "Join game" : "Connecting…"}
          </button>
        </div>
      )}

      {phase === "lobby" && (
        <div className="animate-pop rounded-3xl bg-gradient-to-br from-sky-500 to-cyan-500 p-8 text-center text-white shadow-xl">
          <p className="text-sky-100">You&apos;re in!</p>
          <p className="mt-2 font-display text-4xl">{nickname}</p>
          <p className="mt-4 text-lg">PIN {lobby?.pin}</p>
          <p className="mt-1 text-sky-100">{lobby?.quiz_title}</p>
          <p className="mt-8 animate-pulse-soft text-xl font-bold">
            Waiting for host to start…
          </p>
          <p className="mt-2 text-sky-100">{lobby?.player_count} players in lobby</p>
        </div>
      )}

      {(phase === "question" || phase === "waiting") && question && (
        <div className="animate-slide-up">
          <div className="mb-3 flex items-center justify-between text-sm font-bold text-ink/70">
            <span>
              Q{question.question_index + 1}/{question.total_questions}
            </span>
            <span>{locked ? "Answer locked" : "Tap an answer"}</span>
          </div>
          <TimerBar seconds={question.time_limit} active={!locked} key={question.question_index} />
          <h2 className="mt-5 text-center font-display text-2xl leading-snug sm:text-3xl">
            {question.text}
          </h2>
          {question.image && (
            <img
              src={question.image}
              alt=""
              className="mx-auto mt-4 max-h-40 rounded-xl object-contain"
            />
          )}
          <div className="mt-6 grid grid-cols-2 gap-3">
            {question.options.map((opt, i) => {
              const isSelected = selected === i;
              return (
                <button
                  key={i}
                  type="button"
                  disabled={locked}
                  onClick={() => submit(i)}
                  className={`min-h-28 rounded-2xl p-4 text-left text-lg font-extrabold text-white shadow-md transition active:scale-[0.98] disabled:opacity-80 ${
                    isSelected ? "ring-4 ring-white ring-offset-2 ring-offset-sky-300" : ""
                  }`}
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                >
                  <span className="mb-1 block text-2xl opacity-90">{OPTION_SHAPES[i]}</span>
                  {opt}
                </button>
              );
            })}
          </div>
          {phase === "waiting" && (
            <p className="mt-6 text-center font-bold text-brand-dark animate-pulse-soft">
              Waiting for others…
            </p>
          )}
        </div>
      )}

      {phase === "reveal" && reveal && (
        <div className="animate-pop text-center">
          <p className="font-display text-4xl">
            {lastPoints && lastPoints > 0 ? "Nice!" : "Too bad"}
          </p>
          <p className="mt-2 text-2xl font-extrabold text-brand-dark">
            {lastPoints != null ? `+${lastPoints} pts` : ""}
          </p>
          <div className="mt-6 grid grid-cols-2 gap-2">
            {reveal.options.map((opt, i) => {
              const correct = reveal.correct_indices.includes(i);
              const mine = selected === i;
              return (
                <div
                  key={i}
                  className={`rounded-xl px-3 py-4 text-sm font-bold text-white ${
                    correct ? "ring-4 ring-success" : "opacity-55"
                  } ${mine ? "outline outline-2 outline-offset-2 outline-white" : ""}`}
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                >
                  {opt}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {phase === "leaderboard" && (
        <div>
          <h2 className="mb-4 text-center font-display text-3xl">Standings</h2>
          {myRank && (
            <p className="mb-4 text-center font-bold text-brand-dark">
              You: #{myRank.rank} · {myRank.score} pts
            </p>
          )}
          <Leaderboard entries={leaderboard} highlightSid={mySid} />
        </div>
      )}
    </div>
  );
}
