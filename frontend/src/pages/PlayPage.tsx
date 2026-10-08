import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { clearJoinSession, loadJoinSession, saveJoinSession, useSocket, useSocketEvent } from "../hooks/useSocket";
import { useLang } from "../i18n";
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
  const { t } = useLang();

  const [phase, setPhase] = useState<Phase>("join");
  const [pin, setPin] = useState((params.get("pin") || "").toUpperCase());
  const [nickname, setNickname] = useState("");
  const [studentCode, setStudentCode] = useState("");
  const [requiresCode, setRequiresCode] = useState(false);
  const [teamMode, setTeamMode] = useState(false);
  const [teams, setTeams] = useState<string[]>([]);
  const [team, setTeam] = useState("");
  const [shortText, setShortText] = useState("");
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
  const [reconnecting, setReconnecting] = useState(false);
  const [deviceOffline, setDeviceOffline] = useState(
    typeof navigator !== "undefined" ? !navigator.onLine : false,
  );
  const rejoinedRef = useRef(false);

  useEffect(() => {
    const on = () => setDeviceOffline(false);
    const off = () => setDeviceOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // Prefill from stored session (refresh mid-game).
  useEffect(() => {
    const stored = loadJoinSession();
    if (!stored) return;
    if (!pin && stored.pin) setPin(stored.pin);
    if (!nickname && stored.nickname) setNickname(stored.nickname);
    if (!studentCode && stored.student_code) setStudentCode(stored.student_code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const p = pin.trim().toUpperCase();
    if (p.length < 4) {
      setRequiresCode(false);
      setTeamMode(false);
      setTeams([]);
      return;
    }
    const t = window.setTimeout(() => {
      void api
        .peekPin(p)
        .then((info) => {
          setRequiresCode(info.requires_student_code);
          setTeamMode(!!info.team_mode);
          setTeams(info.teams || []);
        })
        .catch(() => {
          setRequiresCode(false);
          setTeamMode(false);
          setTeams([]);
        });
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
    setReconnecting(false);
    rejoinedRef.current = false;
    saveJoinSession({
      pin: data.pin,
      sid: data.sid,
      nickname: data.nickname || nickname,
      student_code: studentCode.trim().toUpperCase() || undefined,
    });
  });

  useSocketEvent("lobby_update", (data: LobbyState) => {
    setLobby(data);
  });

  useSocketEvent("kicked", (data: { reason: string }) => {
    setError(data.reason || "You were removed from the game");
    setPhase("join");
    setLobby(null);
    clearJoinSession();
    rejoinedRef.current = false;
  });

  useSocketEvent("game_started", () => {
    setPhase("question");
  });

  useSocketEvent("question_started", (data: QuestionPayload) => {
    setQuestion(data);
    setSelected(null);
    setShortText("");
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
    clearJoinSession();
  });

  // Auto-rejoin on (re)connect using stored sid.
  useEffect(() => {
    if (!connected || rejoinedRef.current) return;
    const stored = loadJoinSession();
    if (!stored?.pin) return;
    // Only auto-rejoin if the PIN matches what the user sees (or lobby phase).
    const currentPin = (pin || stored.pin).trim().toUpperCase();
    if (phase === "join" && !pin && stored.pin) setPin(stored.pin);
    if (phase !== "join" || stored.pin === currentPin) {
      rejoinedRef.current = true;
      if (phase !== "join") setReconnecting(true);
      socket.emit("join_game", {
        pin: stored.pin,
        nickname: stored.nickname,
        student_code: stored.student_code || undefined,
        rejoin_sid: stored.sid,
      });
    }
  }, [connected, socket, phase, pin]);

  useEffect(() => {
    if (connected) setReconnecting(false);
    else if (phase !== "join") setReconnecting(true);
  }, [connected, phase]);

  const join = useCallback(() => {
    setError(null);
    socket.emit("join_game", {
      pin: pin.trim().toUpperCase(),
      nickname: nickname.trim(),
      student_code: studentCode.trim().toUpperCase() || undefined,
      team: teamMode ? team || undefined : undefined,
    });
  }, [socket, pin, nickname, studentCode, teamMode, team]);

  const canJoin =
    connected &&
    pin.trim().length >= 4 &&
    (requiresCode ? studentCode.trim().length >= 1 : nickname.trim().length >= 1) &&
    (!teamMode || team.length >= 1);

  const submit = useCallback(
    (optionIndex: number) => {
      if (locked || phase !== "question") return;
      setSelected(optionIndex);
      socket.emit("submit_answer", { option_index: optionIndex });
    },
    [locked, phase, socket],
  );

  const submitShort = useCallback(() => {
    if (locked || phase !== "question" || !shortText.trim()) return;
    setSelected(-1);
    socket.emit("submit_answer", { answer_text: shortText.trim() });
  }, [locked, phase, socket, shortText]);

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
        {final.team_scores && final.team_scores.length > 0 && (
          <div className="mt-6 rounded-2xl border border-sky-200 bg-white p-4">
            <h2 className="text-center font-display text-2xl">Teams</h2>
            <ul className="mt-2 space-y-1">
              {final.team_scores.map((t) => (
                <li key={t.team} className="flex justify-between font-bold">
                  <span>
                    #{t.rank} {t.team}
                  </span>
                  <span>{t.score} pts</span>
                </li>
              ))}
            </ul>
          </div>
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
      {deviceOffline && (
        <p className="mb-3 rounded-xl bg-amber-50 px-3 py-2 text-center text-sm font-bold text-amber-800" role="status">
          You&apos;re offline — the join form stays available and will reconnect automatically.
        </p>
      )}
      {reconnecting && phase !== "join" && (
        <p className="mb-3 rounded-xl bg-amber-50 px-3 py-2 text-center text-sm font-bold text-amber-800 animate-pulse-soft" role="status">
          {connected ? "Rejoining…" : "Connection lost — score kept, reconnecting…"}
        </p>
      )}
      {phase === "join" && (
        <div className="animate-slide-up rounded-3xl border border-sky-200 bg-white p-6 shadow-sm">
          <h1 className="font-display text-4xl">{t.joinTitle}</h1>
          <p className="mt-1 text-ink/70">{t.joinSub}</p>
          {error && (
            <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              {error}
            </p>
          )}
          <label className="mt-6 block">
            <span className="mb-1 block text-sm font-bold">{t.gamePin}</span>
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
              <span className="mb-1 block text-sm font-bold">{t.studentCode}</span>
              <input
                className="w-full rounded-xl border border-sky-200 px-4 py-3 text-lg font-semibold uppercase"
                value={studentCode}
                onChange={(e) => setStudentCode(e.target.value.toUpperCase())}
                maxLength={40}
                placeholder="From your teacher roster"
              />
              <span className="mt-1 block text-xs text-ink/50">
                {t.classGameNote}
              </span>
            </label>
          ) : (
            <label className="mt-4 block">
              <span className="mb-1 block text-sm font-bold">{t.nickname}</span>
              <input
                className="w-full rounded-xl border border-sky-200 px-4 py-3 text-lg font-semibold"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                maxLength={24}
                placeholder="Your name"
              />
            </label>
          )}
          {teamMode && teams.length > 0 && (
            <label className="mt-4 block">
              <span className="mb-1 block text-sm font-bold">{t.team}</span>
              <select
                className="w-full rounded-xl border border-sky-200 px-4 py-3 text-lg font-semibold"
                value={team}
                onChange={(e) => setTeam(e.target.value)}
              >
                <option value="">{t.chooseTeam}</option>
                {teams.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            type="button"
            disabled={!canJoin}
            onClick={join}
            className="mt-6 w-full rounded-2xl bg-brand py-4 text-xl font-extrabold text-white disabled:opacity-50"
          >
            {connected ? t.joinGame : t.connecting}
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
          {question.kind === "short_answer" ? (
            <div className="mt-6">
              <input
                className="w-full rounded-xl border border-sky-200 px-4 py-3 text-lg"
                value={shortText}
                onChange={(e) => setShortText(e.target.value)}
                disabled={locked}
                placeholder="Type your answer"
                maxLength={200}
              />
              <button
                type="button"
                disabled={locked || !shortText.trim()}
                onClick={submitShort}
                className="mt-3 w-full rounded-2xl bg-brand py-3 text-lg font-extrabold text-white disabled:opacity-50"
              >
                {locked ? "Locked" : "Submit answer"}
              </button>
            </div>
          ) : (
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
          )}
          {question.kind === "ordering" && (
            <p className="mt-3 text-center text-xs text-ink/50">
              Ordering — tap the option that comes first (MVP).
            </p>
          )}
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
