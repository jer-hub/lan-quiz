"""Socket.IO event handlers for LanQuiz gameplay."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import socketio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth import decode_socket_token
from app.config import settings
from app.database import AsyncSessionLocal
from app.game_manager import QuestionData, game_manager
from app.models import Assignment, ClassRoom, GameHistory, GameResult, Quiz, Student
from app.utils.qr import generate_qr_data_url

logger = logging.getLogger(__name__)


def register_socket_handlers(sio: socketio.AsyncServer) -> None:
    """Attach all Socket.IO handlers to the server instance."""

    async def emit_error(sid: str, message: str) -> None:
        await sio.emit("error", {"message": message}, to=sid)

    async def broadcast_lobby(session: Any) -> None:
        await sio.emit(
            "lobby_update",
            game_manager.lobby_payload(session),
            room=session.pin,
        )

    async def save_history(session: Any) -> None:
        try:
            results = session.leaderboard()
            async with AsyncSessionLocal() as db:
                row = GameHistory(
                    pin=session.pin,
                    quiz_id=session.quiz_id,
                    quiz_title=session.quiz_title,
                    teacher_id=session.teacher_id,
                    class_id=session.class_id,
                    assignment_id=session.assignment_id,
                    results_json=json.dumps(results, ensure_ascii=False),
                    player_count=session.player_count(),
                )
                db.add(row)
                await db.flush()
                for entry in results:
                    db.add(
                        GameResult(
                            history_id=row.id,
                            student_id=entry.get("student_id"),
                            nickname=entry["nickname"],
                            score=entry["score"],
                            rank=entry["rank"],
                        )
                    )
                await db.commit()
            logger.info("Saved game history pin=%s players=%s", session.pin, session.player_count())
        except Exception:
            logger.exception("Failed to save game history")

    async def run_question_timer(pin: str, time_limit: int) -> None:
        try:
            await asyncio.sleep(time_limit)
            session = game_manager.get_by_pin(pin)
            if not session or session.status.value != "question":
                return
            await finalize_question(session)
        except asyncio.CancelledError:
            return

    async def finalize_question(session: Any) -> None:
        payload = await game_manager.end_question(session)
        await sio.emit("question_ended", payload, room=session.pin)
        await game_manager.set_leaderboard_status(session)
        await sio.emit(
            "leaderboard_update",
            {
                "leaderboard": session.leaderboard(),
                "question_index": session.current_question_index,
                "total_questions": len(session.questions),
            },
            room=session.pin,
        )

    async def start_next_question(host_sid: str) -> None:
        session, question = await game_manager.advance_question(host_sid)
        if question is None:
            await finish_game(session)
            return

        q_payload = {
            "question_index": session.current_question_index,
            "total_questions": len(session.questions),
            "id": question.id,
            "text": question.text,
            "image": question.image,
            "options": question.options,
            "time_limit": question.time_limit,
            "started_at": session.question_started_at,
        }
        await sio.emit("question_started", q_payload, room=session.pin)

        task = asyncio.create_task(run_question_timer(session.pin, question.time_limit))
        session.question_task = task

    async def finish_game(session: Any) -> None:
        ranking = session.leaderboard()
        await sio.emit(
            "game_ended",
            {
                "pin": session.pin,
                "quiz_title": session.quiz_title,
                "leaderboard": ranking,
                "podium": ranking[:3],
            },
            room=session.pin,
        )
        await save_history(session)

    @sio.event
    async def connect(sid: str, environ: dict, auth: Any = None) -> None:
        logger.info("Client connected sid=%s", sid)

    @sio.event
    async def disconnect(sid: str) -> None:
        logger.info("Client disconnected sid=%s", sid)
        session = await game_manager.leave_game(sid)
        if session:
            await broadcast_lobby(session)
            await sio.emit("player_left", {"sid": sid}, room=session.pin)

    @sio.event
    async def create_game(sid: str, data: dict) -> None:
        token = (data or {}).get("token")
        principal = decode_socket_token(token)
        if not principal or principal.role != "teacher" or not principal.user_id:
            await emit_error(sid, "Teachers must be logged in to host a game.")
            return

        assignment_id = data.get("assignment_id")
        quiz_id_raw = data.get("quiz_id")

        async with AsyncSessionLocal() as db:
            class_id = None
            quiz = None
            assignment = None

            if assignment_id is not None:
                try:
                    assignment_id = int(assignment_id)
                except (TypeError, ValueError):
                    await emit_error(sid, "Invalid assignment_id")
                    return
                result = await db.execute(
                    select(Assignment)
                    .join(ClassRoom)
                    .options(
                        selectinload(Assignment.quiz).selectinload(Quiz.questions),
                        selectinload(Assignment.classroom),
                    )
                    .where(
                        Assignment.id == assignment_id,
                        ClassRoom.teacher_id == principal.user_id,
                    )
                )
                assignment = result.scalar_one_or_none()
                if not assignment:
                    await emit_error(sid, "Assignment not found")
                    return
                if assignment.status != "open":
                    await emit_error(sid, "Assignment is closed")
                    return
                due = assignment.due_at
                if due is not None:
                    from datetime import datetime, timezone

                    due_aware = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
                    if due_aware < datetime.now(timezone.utc):
                        await emit_error(
                            sid,
                            "Assignment is past due. Extend the due date to host again.",
                        )
                        return
                quiz = assignment.quiz
                class_id = assignment.class_id
                quiz_id = quiz.id
            else:
                try:
                    quiz_id = int(quiz_id_raw)
                except (TypeError, ValueError):
                    await emit_error(sid, "Invalid quiz_id")
                    return
                result = await db.execute(
                    select(Quiz)
                    .options(selectinload(Quiz.questions))
                    .where(Quiz.id == quiz_id, Quiz.teacher_id == principal.user_id)
                )
                quiz = result.scalar_one_or_none()
                if not quiz:
                    await emit_error(sid, "Quiz not found")
                    return

            if not quiz.questions:
                await emit_error(sid, "Quiz has no questions")
                return

            questions = [
                QuestionData(
                    id=q.id,
                    text=q.text,
                    image=q.image,
                    options=json.loads(q.options_json),
                    correct_indices=json.loads(q.correct_indices_json),
                    time_limit=q.time_limit,
                )
                for q in quiz.questions
            ]
            quiz_title = quiz.title
            quiz_pk = quiz.id
            teacher_id = principal.user_id
            asg_id = assignment.id if assignment else None

        try:
            session = await game_manager.create_game(
                host_sid=sid,
                quiz_id=quiz_pk,
                quiz_title=quiz_title,
                questions=questions,
                teacher_id=teacher_id,
                class_id=class_id,
                assignment_id=asg_id,
            )
        except Exception as exc:
            await emit_error(sid, str(exc))
            return

        await sio.enter_room(sid, session.pin)
        join_url = f"{settings.public_base_url}/play?pin={session.pin}"
        qr = generate_qr_data_url(join_url)
        await sio.emit(
            "game_created",
            {
                "pin": session.pin,
                "join_url": join_url,
                "qr": qr,
                "quiz_title": session.quiz_title,
                "question_count": len(session.questions),
                **game_manager.lobby_payload(session),
            },
            to=sid,
        )
        await broadcast_lobby(session)

    @sio.event
    async def join_game(sid: str, data: dict) -> None:
        pin = str(data.get("pin", "")).strip().upper()
        nickname = str(data.get("nickname", "")).strip()
        student_code = str(data.get("student_code", "")).strip().upper()

        session_peek = game_manager.get_by_pin(pin)
        student_id = None
        resolved_nick = nickname

        if session_peek and session_peek.requires_student_code:
            if not student_code:
                await emit_error(sid, "Enter your student code to join this class game.")
                return
            if not session_peek.class_id:
                await emit_error(sid, "Class game is misconfigured.")
                return
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Student).where(
                        Student.class_id == session_peek.class_id,
                        Student.student_code == student_code,
                    )
                )
                student = result.scalar_one_or_none()
                if not student:
                    await emit_error(sid, "Student code not found in this class roster.")
                    return
                student_id = student.id
                resolved_nick = student.display_name

                # Max attempts for assignment games
                if session_peek.assignment_id:
                    asg_result = await db.execute(
                        select(Assignment).where(Assignment.id == session_peek.assignment_id)
                    )
                    asg = asg_result.scalar_one_or_none()
                    if asg and asg.max_attempts is not None:
                        hist_result = await db.execute(
                            select(GameHistory)
                            .options(selectinload(GameHistory.result_rows))
                            .where(GameHistory.assignment_id == asg.id)
                        )
                        play_count = 0
                        for hist in hist_result.scalars().all():
                            if any(r.student_id == student.id for r in hist.result_rows):
                                play_count += 1
                        if play_count >= asg.max_attempts:
                            await emit_error(
                                sid,
                                f"Max attempts reached ({asg.max_attempts}) for this assignment.",
                            )
                            return

        try:
            session = await game_manager.join_game(
                pin,
                sid,
                resolved_nick,
                student_id=student_id,
                student_code=student_code or None,
            )
        except ValueError as exc:
            await emit_error(sid, str(exc))
            return

        await sio.enter_room(sid, session.pin)
        player = session.players[sid]
        await sio.emit(
            "player_joined",
            {"sid": sid, "nickname": player.nickname, "student_id": player.student_id},
            room=session.pin,
        )
        await sio.emit(
            "joined",
            {
                "pin": session.pin,
                "nickname": player.nickname,
                "sid": sid,
                "student_id": player.student_id,
                **game_manager.lobby_payload(session),
            },
            to=sid,
        )
        await broadcast_lobby(session)

    @sio.event
    async def leave_game(sid: str, data: dict | None = None) -> None:
        existing = game_manager.get_by_sid(sid)
        pin = existing.pin if existing else (data or {}).get("pin", "")
        session = await game_manager.leave_game(sid)
        if pin:
            await sio.leave_room(sid, str(pin).upper())
        if session:
            await sio.emit("player_left", {"sid": sid}, room=session.pin)
            await broadcast_lobby(session)

    @sio.event
    async def kick_player(sid: str, data: dict) -> None:
        target = data.get("sid")
        if not target:
            await emit_error(sid, "Missing player sid")
            return
        try:
            session = await game_manager.kick_player(sid, target)
        except ValueError as exc:
            await emit_error(sid, str(exc))
            return
        await sio.emit("kicked", {"reason": "Host removed you from the game"}, to=target)
        await sio.leave_room(target, session.pin)
        await sio.emit("player_left", {"sid": target}, room=session.pin)
        await broadcast_lobby(session)

    @sio.event
    async def start_game(sid: str, data: dict | None = None) -> None:
        try:
            session = await game_manager.start_game(sid)
        except ValueError as exc:
            await emit_error(sid, str(exc))
            return
        await sio.emit(
            "game_started",
            {"pin": session.pin, "question_count": len(session.questions)},
            room=session.pin,
        )
        await start_next_question(sid)

    @sio.event
    async def next_question(sid: str, data: dict | None = None) -> None:
        session = game_manager.get_by_sid(sid)
        if not session or session.host_sid != sid:
            await emit_error(sid, "Only the host can continue.")
            return
        if session.status.value == "question":
            await finalize_question(session)
            return
        await start_next_question(sid)

    @sio.event
    async def skip_question(sid: str, data: dict | None = None) -> None:
        session = game_manager.get_by_sid(sid)
        if not session or session.host_sid != sid:
            await emit_error(sid, "Only the host can skip.")
            return
        if session.status.value == "question":
            await finalize_question(session)
        await start_next_question(sid)

    @sio.event
    async def end_game(sid: str, data: dict | None = None) -> None:
        try:
            session = await game_manager.end_game(sid)
        except ValueError as exc:
            await emit_error(sid, str(exc))
            return
        await finish_game(session)

    @sio.event
    async def submit_answer(sid: str, data: dict) -> None:
        try:
            option_index = int(data.get("option_index"))
        except (TypeError, ValueError):
            await emit_error(sid, "Invalid option_index")
            return
        try:
            session, record, all_answered = await game_manager.submit_answer(sid, option_index)
        except ValueError as exc:
            await emit_error(sid, str(exc))
            return

        await sio.emit(
            "answer_ack",
            {"option_index": record.option_index, "locked": True},
            to=sid,
        )
        await sio.emit(
            "answer_received",
            {
                "answer_count": len(session.current_answers),
                "player_count": session.player_count(),
            },
            room=session.pin,
        )

        if all_answered:
            await finalize_question(session)
