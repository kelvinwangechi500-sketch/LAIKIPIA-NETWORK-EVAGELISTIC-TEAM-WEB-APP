"""
REST API Routes
================
Used by:
  • Frontend JavaScript (chat sync, attendance AJAX)
  • Service Worker background sync
All endpoints return JSON.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models.chat_message import ChatMessage
from models.announcement import Announcement
from models.attendance import Attendance
from models.user import User
from datetime import datetime

api_bp = Blueprint("api", __name__)


# ── Chat Messages ─────────────────────────────────────────────────────────────

@api_bp.route("/chat/messages")
@login_required
def get_messages():
    """Return last N messages for a room."""
    room = request.args.get("room", "general")
    limit = min(int(request.args.get("limit", 50)), 200)
    messages = (
        ChatMessage.query
        .filter_by(room=room)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit).all()
    )
    return jsonify([_msg_to_dict(m) for m in messages])


@api_bp.route("/chat/send", methods=["POST"])
@login_required
def send_message():
    """Store a single chat message. Used for online send."""
    data = request.get_json(silent=True) or {}
    room = data.get("room", "general")
    body = data.get("body", "").strip()
    client_id = data.get("client_id", "")

    if not body:
        return jsonify({"error": "Empty message"}), 400

    # Deduplicate by client_id
    if client_id and ChatMessage.query.filter_by(client_id=client_id).first():
        return jsonify({"status": "duplicate"}), 200

    msg = ChatMessage(
        room=room,
        sender_id=current_user.id,
        body=body,
        client_id=client_id or None,
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify(_msg_to_dict(msg)), 201


@api_bp.route("/chat/sync", methods=["POST"])
@login_required
def sync_messages():
    """
    Bulk sync from IndexedDB offline queue.
    Expects: { messages: [ {room, body, client_id, created_at}, ... ] }
    """
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    saved = 0

    for m in messages:
        client_id = m.get("client_id", "")
        if client_id and ChatMessage.query.filter_by(client_id=client_id).first():
            continue  # already synced

        msg = ChatMessage(
            room=m.get("room", "general"),
            sender_id=current_user.id,
            body=m.get("body", ""),
            client_id=client_id or None,
        )
        db.session.add(msg)
        saved += 1

    db.session.commit()
    return jsonify({"synced": saved})


# ── Announcements ─────────────────────────────────────────────────────────────

@api_bp.route("/announcements")
@login_required
def get_announcements():
    items = (
        Announcement.query
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(20).all()
    )
    return jsonify([_ann_to_dict(a) for a in items])


# ── Attendance ────────────────────────────────────────────────────────────────

@api_bp.route("/attendance/by-date")
@login_required
def attendance_by_date():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "date param required"}), 400
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    records = Attendance.query.filter_by(meeting_date=query_date).all()
    return jsonify([{
        "user_id": r.user_id,
        "name": r.user.full_name,
        "status": r.status,
    } for r in records])


@api_bp.route("/attendance/member/<int:uid>")
@login_required
def member_attendance(uid):
    # Members can only see own records unless admin/vs
    if current_user.role == "member" and current_user.id != uid:
        return jsonify({"error": "Unauthorized"}), 403

    records = (
        Attendance.query
        .filter_by(user_id=uid)
        .order_by(Attendance.meeting_date.desc())
        .limit(50).all()
    )
    return jsonify([{
        "date": str(r.meeting_date),
        "status": r.status,
        "source": r.source,
    } for r in records])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _msg_to_dict(m):
    return {
        "id": m.id,
        "room": m.room,
        "body": m.body,
        "sender_id": m.sender_id,
        "sender_name": m.sender.full_name if m.sender else "Unknown",
        "client_id": m.client_id,
        "created_at": m.created_at.isoformat(),
    }


def _ann_to_dict(a):
    return {
        "id": a.id,
        "title": a.title,
        "body": a.body,
        "is_pinned": a.is_pinned,
        "author": a.author.full_name if a.author else "",
        "created_at": a.created_at.isoformat(),
    }
