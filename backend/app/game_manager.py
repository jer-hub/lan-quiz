"""In-memory game session manager and scoring."""

from __future__ import annotations

import asyncio
import logging
import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class GameStatus(str, Enum):
    LOBBY = "lobby"
    QUESTION = "question"
    REVEAL = "reveal"
    LEADERBOARD = "leaderboard"
    FINISHED = "finished"


@dataclass
class Player:
    sid: str
    nickname: str
    score: int = 0
    is_host: bool = False
    student_id: int | None = None
    connected: bool = True
    disconnected_at: float | None = None
    team: str | None = None


@dataclass
class QuestionData:
    id: int
    text: str
    image: str | None
    options: list[str]
    correct_indices: list[int]
    time_limit: int
    kind: str = "mc"
    answer_text: str | None = None


@dataclass
class AnswerRecord:
    option_index: int
    elapsed_ms: int
    correct: bool
    points: int
    answered_at: float


@dataclass
class GameSession:
    pin: str
    quiz_id: int
    quiz_title: str
    host_sid: str
    questions: list[QuestionData]
    status: GameStatus = GameStatus.LOBBY
    current_question_index: int = -1
    players: dict[str, Player] = field(default_factory=dict)
    current_answers: dict[str, AnswerRecord] = field(default_factory=dict)
    question_started_at: float | None = None
    question_task: asyncio.Task | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    teacher_id: int | None = None
    class_id: int | None = None
    assignment_id: int | None = None
    requires_student_code: bool = False
    team_mode: bool = False
    teams: list[str] = field(default_factory=list)
    # Per-player shuffle: sid -> order where order[new_idx] = old_idx.
    option_map: dict[str, list[int]] = field(default_factory=dict)
    # Accumulated per-question reveal summaries for item analysis.
    question_history: list[dict[str, Any]] = field(default_factory=list)

    def public_players(self) -> list[dict[str, Any]]:
        return [
            {
                "sid": p.sid,
                "nickname": p.nickname,
                "score": p.score,
                "is_host": p.is_host,
                "student_id": p.student_id,
                "connected": p.connected,
                "team": p.team,
            }
            for p in self.players.values()
            if not p.is_host
        ]

    def leaderboard(self) -> list[dict[str, Any]]:
        ranked = sorted(
            [p for p in self.players.values() if not p.is_host],
            key=lambda p: (-p.score, p.nickname.lower()),
        )
        return [
            {
                "rank": i + 1,
                "sid": p.sid,
                "nickname": p.nickname,
                "score": p.score,
                "student_id": p.student_id,
                "team": p.team,
            }
            for i, p in enumerate(ranked)
        ]

    def team_scores(self) -> list[dict[str, Any]]:
        totals: dict[str, int] = {}
        counts: dict[str, int] = {}
        for p in self.players.values():
            if p.is_host or not p.team:
                continue
            totals[p.team] = totals.get(p.team, 0) + p.score
            counts[p.team] = counts.get(p.team, 0) + 1
        ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        return [
            {"rank": i + 1, "team": team, "score": score, "players": counts.get(team, 0)}
            for i, (team, score) in enumerate(ranked)
        ]

    def shuffled_for(self, sid: str, question: QuestionData) -> tuple[list[str], list[int]]:
        """Per-player option order for MC; other kinds return canonical."""
        from app.utils.shuffle import shuffle_options

        if question.kind != "mc" or len(question.options) <= 1:
            return list(question.options), list(question.correct_indices)
        order = self.option_map.get(sid)
        if order is None or len(order) != len(question.options):
            _, _, order = shuffle_options(question.options, question.correct_indices)
            self.option_map[sid] = order
        shuffled = [question.options[i] for i in order]
        remap = {old: new for new, old in enumerate(order)}
        new_correct = sorted({remap[i] for i in question.correct_indices if i in remap})
        return shuffled, new_correct

    def player_count(self) -> int:
        return sum(1 for p in self.players.values() if not p.is_host)

    def connected_count(self) -> int:
        return sum(1 for p in self.players.values() if not p.is_host and p.connected)

    def to_snapshot(self) -> dict[str, Any]:
        """JSON-serializable snapshot for ActiveGame persistence."""
        return {
            "pin": self.pin,
            "quiz_id": self.quiz_id,
            "quiz_title": self.quiz_title,
            "teacher_id": self.teacher_id,
            "class_id": self.class_id,
            "assignment_id": self.assignment_id,
            "requires_student_code": self.requires_student_code,
            "status": self.status.value,
            "current_question_index": self.current_question_index,
            "team_mode": self.team_mode,
            "teams": list(self.teams),
            "question_history": [dict(h) for h in self.question_history],
            "questions": [
                {
                    "id": q.id,
                    "text": q.text,
                    "image": q.image,
                    "options": q.options,
                    "correct_indices": q.correct_indices,
                    "time_limit": q.time_limit,
                    "kind": q.kind,
                    "answer_text": q.answer_text,
                }
                for q in self.questions
            ],
            "players": [
                {
                    "sid": p.sid,
                    "nickname": p.nickname,
                    "score": p.score,
                    "is_host": p.is_host,
                    "student_id": p.student_id,
                    "team": p.team,
                    "connected": False,  # all sockets die on restart
                    "disconnected_at": None,
                }
                for p in self.players.values()
            ],
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any], *, host_sid: str = "") -> GameSession:
        questions = [
            QuestionData(
                id=q["id"],
                text=q["text"],
                image=q.get("image"),
                options=list(q.get("options", [])),
                correct_indices=list(q.get("correct_indices", [])),
                time_limit=int(q.get("time_limit", 20)),
                kind=str(q.get("kind", "mc")),
                answer_text=q.get("answer_text"),
            )
            for q in data.get("questions", [])
        ]
        status_raw = str(data.get("status", "lobby"))
        # Never restore mid-question timers: pause on leaderboard (host advances).
        if status_raw == "question":
            status_raw = "leaderboard"
        session = cls(
            pin=str(data["pin"]).upper(),
            quiz_id=int(data["quiz_id"]),
            quiz_title=str(data.get("quiz_title", "")),
            host_sid=host_sid,
            questions=questions,
            status=GameStatus(status_raw),
            current_question_index=int(data.get("current_question_index", -1)),
            teacher_id=data.get("teacher_id"),
            class_id=data.get("class_id"),
            assignment_id=data.get("assignment_id"),
            requires_student_code=bool(data.get("requires_student_code", False)),
            team_mode=bool(data.get("team_mode", False)),
            teams=list(data.get("teams", []) or []),
        )
        for p in data.get("players", []):
            sid = str(p.get("sid", ""))
            if not sid:
                continue
            is_host = bool(p.get("is_host", False))
            session.players[sid] = Player(
                sid=sid if not is_host else host_sid or sid,
                nickname=str(p.get("nickname", "Host" if is_host else "?")),
                score=int(p.get("score", 0)),
                is_host=is_host,
                student_id=p.get("student_id"),
                connected=False,
                disconnected_at=None,
                team=p.get("team"),
            )
        session.question_history = list(data.get("question_history", []) or [])
        return session


def normalize_short_answer(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def calculate_score(elapsed_ms: int, time_limit_s: int, correct: bool) -> int:
    """Kahoot-style scoring.

    Formula (correct answers only):
        points = round(BASE * (1 - (elapsed / time_limit) / 2))
        clamped to [BASE // 2, BASE]

    Wrong answers score 0.
    Faster correct answers earn more points (up to BASE).
    """
    if not correct:
        return 0
    base = settings.score_base
    time_limit_ms = max(time_limit_s, 1) * 1000
    ratio = min(max(elapsed_ms / time_limit_ms, 0.0), 1.0)
    points = round(base * (1 - ratio / 2))
    return max(base // 2, min(base, points))


class GameManager:
    """Manages active in-memory game sessions keyed by PIN."""

    def __init__(self) -> None:
        self._games: dict[str, GameSession] = {}
        self._sid_to_pin: dict[str, str] = {}
        self._lock = asyncio.Lock()

    def _generate_pin(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        # Avoid ambiguous characters
        alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
        for _ in range(50):
            pin = "".join(random.choices(alphabet, k=6))
            if pin not in self._games:
                return pin
        raise RuntimeError("Could not generate unique PIN")

    async def create_game(
        self,
        *,
        host_sid: str,
        quiz_id: int,
        quiz_title: str,
        questions: list[QuestionData],
        teacher_id: int | None = None,
        class_id: int | None = None,
        assignment_id: int | None = None,
        team_mode: bool = False,
        teams: list[str] | None = None,
    ) -> GameSession:
        async with self._lock:
            old_pin = self._sid_to_pin.get(host_sid)
            if old_pin and old_pin in self._games:
                await self._cleanup_game_unlocked(old_pin)

            pin = self._generate_pin()
            clean_teams = [t.strip()[:24] for t in (teams or []) if t.strip()][:8]
            session = GameSession(
                pin=pin,
                quiz_id=quiz_id,
                quiz_title=quiz_title,
                host_sid=host_sid,
                questions=questions,
                teacher_id=teacher_id,
                class_id=class_id,
                assignment_id=assignment_id,
                requires_student_code=assignment_id is not None,
                team_mode=bool(team_mode) and len(clean_teams) >= 2,
                teams=clean_teams,
            )
            host = Player(sid=host_sid, nickname="Host", is_host=True)
            session.players[host_sid] = host
            self._games[pin] = session
            self._sid_to_pin[host_sid] = pin
            logger.info(
                "Game created pin=%s quiz=%s host=%s assignment=%s",
                pin,
                quiz_id,
                host_sid,
                assignment_id,
            )
            return session

    def get_by_pin(self, pin: str) -> GameSession | None:
        return self._games.get(pin.upper())

    def get_by_assignment_id(self, assignment_id: int) -> GameSession | None:
        for session in self._games.values():
            if session.assignment_id == assignment_id:
                return session
        return None

    def get_by_sid(self, sid: str) -> GameSession | None:
        pin = self._sid_to_pin.get(sid)
        if not pin:
            return None
        return self._games.get(pin)

    REJOIN_GRACE_S = 60.0

    async def join_game(
        self,
        pin: str,
        sid: str,
        nickname: str,
        *,
        student_id: int | None = None,
        student_code: str | None = None,
        rejoin_sid: str | None = None,
        team: str | None = None,
    ) -> GameSession:
        async with self._lock:
            session = self._games.get(pin.upper())
            if not session:
                raise ValueError("Game not found. Check the PIN and try again.")
            if session.status not in (GameStatus.LOBBY, GameStatus.LEADERBOARD):
                # LEADERBOARD = restored mid-game pause: allow rejoin, host advances.
                if session.status != GameStatus.LEADERBOARD:
                    raise ValueError("Game already started. You cannot join now.")

            nick = nickname.strip()[:24]
            if len(nick) < 1:
                raise ValueError("Nickname is required.")

            # --- Reclaim path: same student or explicit/disconnected sid ---
            reclaimed_from: str | None = None
            if session.requires_student_code:
                if not student_id:
                    raise ValueError("This is a class game. Enter your student code.")
                for old_sid, p in list(session.players.items()):
                    if not p.is_host and p.student_id == student_id and old_sid != sid:
                        if not p.connected or (rejoin_sid and rejoin_sid == old_sid):
                            reclaimed_from = old_sid
                            nick = p.nickname  # roster name wins
                            break
                        raise ValueError("This student is already in the lobby.")
            else:
                if rejoin_sid and rejoin_sid in session.players:
                    old = session.players[rejoin_sid]
                    if not old.is_host and old.nickname.lower() == nick.lower():
                        reclaimed_from = rejoin_sid
                if reclaimed_from is None:
                    for old_sid, p in list(session.players.items()):
                        if not p.is_host and not p.connected and p.nickname.lower() == nick.lower():
                            reclaimed_from = old_sid
                            break

            if reclaimed_from is not None:
                old = session.players.pop(reclaimed_from)
                session.current_answers.pop(reclaimed_from, None)
                self._sid_to_pin.pop(reclaimed_from, None)
                old_pin = self._sid_to_pin.get(sid)
                if old_pin and old_pin != session.pin and old_pin in self._games:
                    self._games[old_pin].players.pop(sid, None)
                    self._sid_to_pin.pop(sid, None)
                session.players[sid] = Player(
                    sid=sid, nickname=old.nickname, score=old.score,
                    student_id=old.student_id, connected=True, disconnected_at=None,
                    team=old.team,
                )
                self._sid_to_pin[sid] = session.pin
                logger.info(
                    "Player rejoined pin=%s nick=%s old=%s new=%s",
                    session.pin, old.nickname, reclaimed_from, sid,
                )
                return session

            # --- Fresh join path ---
            if session.status != GameStatus.LOBBY:
                raise ValueError("Game already started. You cannot join now.")
            if session.player_count() >= 100:
                raise ValueError("Game is full.")

            if session.requires_student_code and not student_id:
                raise ValueError("This is a class game. Enter your student code.")
            existing = {
                p.nickname.lower()
                for p in session.players.values()
                if not p.is_host and p.connected
            }
            if nick.lower() in existing:
                raise ValueError("Nickname already taken in this game.")

            team_clean: str | None = None
            if session.team_mode:
                if not team or not team.strip():
                    raise ValueError("Choose a team to join.")
                want = team.strip()[:24]
                if want not in session.teams:
                    raise ValueError("Unknown team.")
                team_clean = want

            old_pin = self._sid_to_pin.get(sid)
            if old_pin and old_pin != session.pin and old_pin in self._games:
                old = self._games[old_pin]
                old.players.pop(sid, None)
                self._sid_to_pin.pop(sid, None)

            session.players[sid] = Player(
                sid=sid, nickname=nick, student_id=student_id, team=team_clean
            )
            self._sid_to_pin[sid] = session.pin
            logger.info(
                "Player joined pin=%s nick=%s sid=%s student=%s code=%s",
                session.pin,
                nick,
                sid,
                student_id,
                student_code,
            )
            return session

    async def leave_game(self, sid: str) -> GameSession | None:
        """Explicit leave: remove immediately."""
        async with self._lock:
            pin = self._sid_to_pin.pop(sid, None)
            if not pin:
                return None
            session = self._games.get(pin)
            if not session:
                return None
            player = session.players.pop(sid, None)
            if player and player.is_host:
                await self._cleanup_game_unlocked(pin)
                return None
            session.current_answers.pop(sid, None)
            session.option_map.pop(sid, None)
            logger.info("Player left pin=%s sid=%s", pin, sid)
            return session

    async def mark_disconnected(self, sid: str) -> GameSession | None:
        """Grace-period disconnect: keep slot 60s for rejoin."""
        async with self._lock:
            pin = self._sid_to_pin.pop(sid, None)
            if not pin:
                return None
            session = self._games.get(pin)
            if not session:
                return None
            player = session.players.get(sid)
            if not player:
                return None
            if player.is_host:
                # Host drop keeps the lobby; host reclaims via reclaim_game.
                player.connected = False
                try:
                    loop = asyncio.get_event_loop()
                    player.disconnected_at = loop.time()
                except RuntimeError:
                    player.disconnected_at = None
                logger.info("Host disconnected pin=%s sid=%s (awaiting reclaim)", pin, sid)
                return session
            player.connected = False
            try:
                loop = asyncio.get_event_loop()
                player.disconnected_at = loop.time()
            except RuntimeError:
                player.disconnected_at = None
            session.current_answers.pop(sid, None)
            logger.info("Player disconnected pin=%s sid=%s (60s grace)", pin, sid)
            return session

    async def reclaim_host(self, pin: str, new_sid: str, teacher_id: int) -> GameSession:
        async with self._lock:
            session = self._games.get(pin.upper())
            if not session:
                raise ValueError("Game not found. It may have ended.")
            if session.teacher_id is not None and session.teacher_id != teacher_id:
                raise ValueError("Only the hosting teacher can reclaim this game.")
            old_sid = session.host_sid
            old_host = session.players.pop(old_sid, None)
            self._sid_to_pin.pop(old_sid, None)
            old_pin = self._sid_to_pin.get(new_sid)
            if old_pin and old_pin != session.pin and old_pin in self._games:
                self._games[old_pin].players.pop(new_sid, None)
                self._sid_to_pin.pop(new_sid, None)
            session.host_sid = new_sid
            session.players[new_sid] = Player(
                sid=new_sid, nickname="Host", is_host=True, connected=True
            )
            self._sid_to_pin[new_sid] = session.pin
            if old_host is not None:
                logger.info("Host reclaimed pin=%s old=%s new=%s", session.pin, old_sid, new_sid)
            return session

    def inject_restored(self, session: GameSession) -> None:
        """Insert a snapshot-restored session (startup only, no lock needed)."""
        self._games[session.pin] = session
        # Old sids are stale; do not populate _sid_to_pin (forces reclaim path).

    async def kick_player(self, host_sid: str, target_sid: str) -> GameSession:
        async with self._lock:
            session = self.get_by_sid(host_sid)
            if not session or session.host_sid != host_sid:
                raise ValueError("Only the host can kick players.")
            if target_sid == host_sid:
                raise ValueError("Cannot kick the host.")
            if target_sid not in session.players:
                raise ValueError("Player not found.")
            session.players.pop(target_sid)
            session.current_answers.pop(target_sid, None)
            self._sid_to_pin.pop(target_sid, None)
            return session

    async def start_game(self, host_sid: str) -> GameSession:
        async with self._lock:
            session = self.get_by_sid(host_sid)
            if not session or session.host_sid != host_sid:
                raise ValueError("Only the host can start the game.")
            if session.status != GameStatus.LOBBY:
                raise ValueError("Game already started.")
            if session.player_count() < 1:
                raise ValueError("Need at least one player to start.")
            if not session.questions:
                raise ValueError("Quiz has no questions.")
            session.status = GameStatus.QUESTION
            session.current_question_index = -1
            return session

    def get_current_question(self, session: GameSession) -> QuestionData | None:
        idx = session.current_question_index
        if idx < 0 or idx >= len(session.questions):
            return None
        return session.questions[idx]

    async def advance_question(self, host_sid: str) -> tuple[GameSession, QuestionData | None]:
        """Move to next question. Returns (session, question) or (session, None) if finished."""
        async with self._lock:
            session = self.get_by_sid(host_sid)
            if not session or session.host_sid != host_sid:
                raise ValueError("Only the host can advance questions.")
            if session.question_task and not session.question_task.done():
                session.question_task.cancel()
                session.question_task = None

            next_idx = session.current_question_index + 1
            if next_idx >= len(session.questions):
                session.status = GameStatus.FINISHED
                session.current_answers.clear()
                return session, None

            session.current_question_index = next_idx
            session.status = GameStatus.QUESTION
            session.current_answers.clear()
            session.question_started_at = asyncio.get_event_loop().time()
            # Build per-player shuffle map for MC (deterministic per PIN+index).
            question = session.questions[next_idx]
            session.option_map.clear()
            if question.kind == "mc" and len(question.options) > 1:
                from app.utils.shuffle import shuffle_options

                for psid, p in session.players.items():
                    if p.is_host:
                        continue
                    seed = hash((session.pin, next_idx, psid)) & 0xFFFFFFFF
                    _, _, order = shuffle_options(
                        question.options, question.correct_indices, seed=seed
                    )
                    session.option_map[psid] = order
            return session, question

    async def submit_answer(
        self, sid: str, option_index: int | None = None, answer_text: str | None = None
    ) -> tuple[GameSession, AnswerRecord, bool]:
        """Submit answer. Returns (session, record, all_answered)."""
        async with self._lock:
            session = self.get_by_sid(sid)
            if not session:
                raise ValueError("You are not in a game.")
            player = session.players.get(sid)
            if not player or player.is_host:
                raise ValueError("Hosts cannot answer.")
            if session.status != GameStatus.QUESTION:
                raise ValueError("No active question.")
            if sid in session.current_answers:
                raise ValueError("Answer already submitted.")

            question = self.get_current_question(session)
            if not question:
                raise ValueError("No active question.")

            now = asyncio.get_event_loop().time()
            started = session.question_started_at or now
            elapsed_ms = int((now - started) * 1000)
            # Reject answers past time limit (+ small grace)
            if elapsed_ms > question.time_limit * 1000 + 500:
                raise ValueError("Time is up.")

            if question.kind == "short_answer":
                if not answer_text or not answer_text.strip():
                    raise ValueError("Answer is required.")
                correct = (
                    normalize_short_answer(answer_text)
                    == normalize_short_answer(question.answer_text or "")
                )
                canonical_idx = -1
            elif question.kind == "ordering":
                if option_index is None or not 0 <= option_index < len(question.options):
                    # Ordering uses single-tap position; validate range.
                    raise ValueError("Invalid option.")
                # Ordering: only exact position 0 (canonical first) scores; frontend
                # sends the tapped position in canonical order (no shuffle for ordering).
                canonical_idx = int(option_index)
                correct = canonical_idx in question.correct_indices
            else:
                if option_index is None or option_index < 0:
                    raise ValueError("Invalid option.")
                # Translate per-player shuffle back to canonical.
                order = session.option_map.get(sid)
                if order and len(order) == len(question.options):
                    if option_index >= len(order):
                        raise ValueError("Invalid option.")
                    from app.utils.shuffle import unshuffle_index

                    canonical_idx = unshuffle_index(int(option_index), order)
                else:
                    canonical_idx = int(option_index)
                if canonical_idx < 0 or canonical_idx >= len(question.options):
                    raise ValueError("Invalid option.")
                # true_false is MC with 2 options; same path.
                correct = canonical_idx in question.correct_indices

            points = calculate_score(elapsed_ms, question.time_limit, correct)
            record = AnswerRecord(
                option_index=canonical_idx,
                elapsed_ms=elapsed_ms,
                correct=correct,
                points=points,
                answered_at=now,
            )
            session.current_answers[sid] = record
            player.score += points

            all_answered = len(session.current_answers) >= session.player_count()
            return session, record, all_answered

    async def end_question(self, session: GameSession) -> dict[str, Any]:
        """Finalize current question and build reveal payload."""
        async with self._lock:
            if session.question_task and not session.question_task.done():
                session.question_task.cancel()
                session.question_task = None
            session.status = GameStatus.REVEAL
            question = self.get_current_question(session)
            if not question:
                return {"error": "No question"}

            results = []
            for sid, player in session.players.items():
                if player.is_host:
                    continue
                ans = session.current_answers.get(sid)
                results.append(
                    {
                        "sid": sid,
                        "nickname": player.nickname,
                        "answered": ans is not None,
                        "option_index": ans.option_index if ans else None,
                        "correct": ans.correct if ans else False,
                        "points": ans.points if ans else 0,
                        "score": player.score,
                    }
                )

            session.question_history.append(
                {
                    "question_index": session.current_question_index,
                    "question_id": question.id,
                    "text": question.text,
                    "kind": question.kind,
                    "options": list(question.options),
                    "correct_indices": list(question.correct_indices),
                    "results": [
                        {
                            "sid": r["sid"],
                            "correct": r["correct"],
                            "option_index": r["option_index"],
                        }
                        for r in results
                    ],
                }
            )

            return {
                "question_index": session.current_question_index,
                "correct_indices": question.correct_indices,
                "options": question.options,
                "kind": question.kind,
                "answer_text": question.answer_text,
                "results": results,
                "leaderboard": session.leaderboard(),
                "team_scores": session.team_scores() if session.team_mode else [],
                "answer_count": len(session.current_answers),
                "player_count": session.player_count(),
            }

    async def set_leaderboard_status(self, session: GameSession) -> None:
        async with self._lock:
            if session.status != GameStatus.FINISHED:
                session.status = GameStatus.LEADERBOARD

    async def end_game(self, host_sid: str) -> GameSession:
        async with self._lock:
            session = self.get_by_sid(host_sid)
            if not session or session.host_sid != host_sid:
                raise ValueError("Only the host can end the game.")
            if session.question_task and not session.question_task.done():
                session.question_task.cancel()
                session.question_task = None
            session.status = GameStatus.FINISHED
            return session

    async def cleanup_game(self, pin: str) -> None:
        async with self._lock:
            await self._cleanup_game_unlocked(pin)

    async def _cleanup_game_unlocked(self, pin: str) -> None:
        session = self._games.pop(pin, None)
        if not session:
            return
        if session.question_task and not session.question_task.done():
            session.question_task.cancel()
        for sid in list(session.players.keys()):
            self._sid_to_pin.pop(sid, None)
        logger.info("Game cleaned up pin=%s", pin)

    def lobby_payload(self, session: GameSession) -> dict[str, Any]:
        return {
            "pin": session.pin,
            "status": session.status.value,
            "quiz_title": session.quiz_title,
            "quiz_id": session.quiz_id,
            "players": session.public_players(),
            "player_count": session.player_count(),
            "question_count": len(session.questions),
            "current_question_index": session.current_question_index,
            "requires_student_code": session.requires_student_code,
            "assignment_id": session.assignment_id,
            "class_id": session.class_id,
            "team_mode": session.team_mode,
            "teams": list(session.teams),
            "team_scores": session.team_scores() if session.team_mode else [],
        }


game_manager = GameManager()
