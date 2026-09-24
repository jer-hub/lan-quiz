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


@dataclass
class QuestionData:
    id: int
    text: str
    image: str | None
    options: list[str]
    correct_indices: list[int]
    time_limit: int


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

    def public_players(self) -> list[dict[str, Any]]:
        return [
            {
                "sid": p.sid,
                "nickname": p.nickname,
                "score": p.score,
                "is_host": p.is_host,
                "student_id": p.student_id,
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
            }
            for i, p in enumerate(ranked)
        ]

    def player_count(self) -> int:
        return sum(1 for p in self.players.values() if not p.is_host)


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
    ) -> GameSession:
        async with self._lock:
            old_pin = self._sid_to_pin.get(host_sid)
            if old_pin and old_pin in self._games:
                await self._cleanup_game_unlocked(old_pin)

            pin = self._generate_pin()
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

    async def join_game(
        self,
        pin: str,
        sid: str,
        nickname: str,
        *,
        student_id: int | None = None,
        student_code: str | None = None,
    ) -> GameSession:
        async with self._lock:
            session = self._games.get(pin.upper())
            if not session:
                raise ValueError("Game not found. Check the PIN and try again.")
            if session.status != GameStatus.LOBBY:
                raise ValueError("Game already started. You cannot join now.")
            if session.player_count() >= 100:
                raise ValueError("Game is full.")

            if session.requires_student_code:
                if not student_id:
                    raise ValueError("This is a class game. Enter your student code.")
                for p in session.players.values():
                    if not p.is_host and p.student_id == student_id:
                        raise ValueError("This student is already in the lobby.")

            nick = nickname.strip()[:24]
            if len(nick) < 1:
                raise ValueError("Nickname is required.")
            existing = {
                p.nickname.lower()
                for p in session.players.values()
                if not p.is_host
            }
            if nick.lower() in existing:
                raise ValueError("Nickname already taken in this game.")

            old_pin = self._sid_to_pin.get(sid)
            if old_pin and old_pin != session.pin and old_pin in self._games:
                old = self._games[old_pin]
                old.players.pop(sid, None)
                self._sid_to_pin.pop(sid, None)

            session.players[sid] = Player(
                sid=sid, nickname=nick, student_id=student_id
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
            logger.info("Player left pin=%s sid=%s", pin, sid)
            return session

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
            return session, session.questions[next_idx]

    async def submit_answer(
        self, sid: str, option_index: int
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
            if option_index < 0 or option_index >= len(question.options):
                raise ValueError("Invalid option.")

            now = asyncio.get_event_loop().time()
            started = session.question_started_at or now
            elapsed_ms = int((now - started) * 1000)
            # Reject answers past time limit (+ small grace)
            if elapsed_ms > question.time_limit * 1000 + 500:
                raise ValueError("Time is up.")

            correct = option_index in question.correct_indices
            points = calculate_score(elapsed_ms, question.time_limit, correct)
            record = AnswerRecord(
                option_index=option_index,
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

            return {
                "question_index": session.current_question_index,
                "correct_indices": question.correct_indices,
                "options": question.options,
                "results": results,
                "leaderboard": session.leaderboard(),
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
        }


game_manager = GameManager()
