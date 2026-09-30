"""
Chat Routes - HTTP endpoints for chat pages and file uploads
"""
import os, uuid
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from models.user import User
from models.chat_message import ChatMessage, MessageRead, ChatRoom
from datetime import datetime

chat_bp = Blueprint("chat", __name__)

ALLOWED = {"png","jpg","jpeg","gif","webp","pdf","mp3","wav","ogg","m4a","webm","mp4"}

def allowed(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED

def get_msg_type(filename):
    ext = filename.rsplit(".",1)[1].lower()
    if ext in {"png","jpg","jpeg","gif","webp"}: return "image"
    if ext == "pdf": return "pdf"
    if ext in {"mp3","wav","ogg","m4a","webm","mp4"}: return "audio"
    return "file"

def dm_room_id(uid1, uid2):
    return f"dm_{min(uid1,uid2)}_{max(uid1,uid2)}"

def unread_count(room_id, user_id):
    last_read = (
        MessageRead.query
        .join(ChatMessage, MessageRead.message_id == ChatMessage.id)
        .filter(ChatMessage.room == room_id, MessageRead.user_id == user_id)
        .order_by(MessageRead.read_at.desc())
        .first()
    )
    q = ChatMessage.query.filter(
        ChatMessage.room == room_id,
        ChatMessage.sender_id != user_id,
        ChatMessage.is_deleted == False
    )
    if last_read:
        q = q.filter(ChatMessage.created_at > last_read.read_at)
    return q.count()

# ── Main chat page ─────────────────────────────────────────────────────────────
@chat_bp.route("/")
@login_required
def index():
    # Group rooms
    group_rooms = ChatRoom.query.filter_by(room_type="group").all()
    rooms_data = []
    for room in group_rooms:
        last_msg = (ChatMessage.query
            .filter_by(room=room.room_id, is_deleted=False)
            .order_by(ChatMessage.created_at.desc()).first())
        rooms_data.append({
            "room_id": room.room_id,
            "name": room.name,
            "type": "group",
            "last_msg": last_msg.body[:50] if last_msg else "No messages yet",
            "last_time": last_msg.created_at.strftime("%H:%M") if last_msg else "",
            "unread": unread_count(room.room_id, current_user.id),
        })

    # DM conversations
    all_members = User.query.filter(
        User.id != current_user.id,
        User.is_active == True
    ).order_by(User.full_name).all()

    dm_data = []
    for member in all_members:
        rid = dm_room_id(current_user.id, member.id)
        last_msg = (ChatMessage.query
            .filter_by(room=rid, is_deleted=False)
            .order_by(ChatMessage.created_at.desc()).first())
        if last_msg:  # only show DMs that have messages
            dm_data.append({
                "room_id": rid,
                "name": member.full_name,
                "user_id": member.id,
                "type": "dm",
                "avatar": member.full_name[0].upper(),
                "last_msg": last_msg.body[:50],
                "last_time": last_msg.created_at.strftime("%H:%M"),
                "unread": unread_count(rid, current_user.id),
                "online": member.last_seen and (datetime.utcnow() - member.last_seen).seconds < 300,
            })

    return render_template("chat/index.html",
        group_rooms=rooms_data,
        dm_data=dm_data,
        all_members=all_members,
        current_user=current_user)


# ── Get messages for a room ───────────────────────────────────────────────────
@chat_bp.route("/messages/<room_id>")
@login_required
def get_messages(room_id):
    before_id = request.args.get("before", type=int)
    limit = 50
    q = ChatMessage.query.filter_by(room=room_id, is_deleted=False)
    if before_id:
        q = q.filter(ChatMessage.id < before_id)
    messages = q.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    messages.reverse()

    # Mark all as read
    for msg in messages:
        if msg.sender_id != current_user.id:
            if not MessageRead.query.filter_by(message_id=msg.id, user_id=current_user.id).first():
                db.session.add(MessageRead(message_id=msg.id, user_id=current_user.id))
    db.session.commit()

    return jsonify([_msg_dict(m) for m in messages])


# ── Upload file ───────────────────────────────────────────────────────────────
@chat_bp.route("/upload", methods=["POST"])
@login_required
def upload_file():
    file = request.files.get("file")
    room_id = request.form.get("room_id", "general")
    reply_to = request.form.get("reply_to", type=int)

    if not file or not file.filename:
        return jsonify({"error": "No file"}), 400
    if not allowed(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 20 * 1024 * 1024:
        return jsonify({"error": "Max file size is 20MB"}), 400

    ext = file.filename.rsplit(".",1)[1].lower()
    fname = f"chat_{uuid.uuid4().hex[:12]}.{ext}"
    file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], fname))

    msg_type = get_msg_type(file.filename)
    msg = ChatMessage(
        room=room_id,
        sender_id=current_user.id,
        body=file.filename,
        msg_type=msg_type,
        file_url=f"/uploads/{fname}",
        file_name=file.filename,
        file_size=size,
        reply_to_id=reply_to,
        client_id=str(uuid.uuid4()),
    )
    db.session.add(msg)
    db.session.commit()

    # Emit via socket
    from extensions import socketio
    socketio.emit("new_message", _msg_dict(msg), room=room_id)

    return jsonify(_msg_dict(msg)), 201


# ── Delete message ────────────────────────────────────────────────────────────
@chat_bp.route("/message/<int:mid>/delete", methods=["POST"])
@login_required
def delete_message(mid):
    msg = ChatMessage.query.get_or_404(mid)
    if msg.sender_id != current_user.id and current_user.role != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    msg.is_deleted = True
    msg.body = "This message was deleted"
    db.session.commit()
    from extensions import socketio
    socketio.emit("message_deleted", {"id": mid, "room": msg.room}, room=msg.room)
    return jsonify({"success": True})


# ── Get all members for new DM ────────────────────────────────────────────────
@chat_bp.route("/members")
@login_required
def get_members():
    members = User.query.filter(
        User.id != current_user.id, User.is_active == True
    ).order_by(User.full_name).all()
    return jsonify([{
        "id": m.id,
        "name": m.full_name,
        "avatar": m.full_name[0].upper(),
        "role": m.role,
        "online": m.last_seen and (datetime.utcnow() - m.last_seen).seconds < 300,
    } for m in members])


# ── Read receipt ──────────────────────────────────────────────────────────────
@chat_bp.route("/read/<room_id>", methods=["POST"])
@login_required
def mark_read(room_id):
    messages = ChatMessage.query.filter(
        ChatMessage.room == room_id,
        ChatMessage.sender_id != current_user.id,
        ChatMessage.is_deleted == False
    ).all()
    for msg in messages:
        if not MessageRead.query.filter_by(message_id=msg.id, user_id=current_user.id).first():
            db.session.add(MessageRead(message_id=msg.id, user_id=current_user.id))
    db.session.commit()
    return jsonify({"ok": True})


def _msg_dict(m):
    reads = MessageRead.query.filter_by(message_id=m.id).count()
    return {
        "id": m.id,
        "room": m.room,
        "body": m.body,
        "msg_type": m.msg_type,
        "file_url": m.file_url,
        "file_name": m.file_name,
        "file_size": m.file_size,
        "sender_id": m.sender_id,
        "sender_name": m.sender.full_name if m.sender else "Unknown",
        "sender_avatar": m.sender.full_name[0].upper() if m.sender else "?",
        "reply_to": {
            "id": m.reply_to.id,
            "body": m.reply_to.body[:60],
            "sender": m.reply_to.sender.full_name if m.reply_to and m.reply_to.sender else ""
        } if m.reply_to else None,
        "is_deleted": m.is_deleted,
        "read_count": reads,
        "created_at": m.created_at.isoformat(),
        "time": m.created_at.strftime("%H:%M"),
    }
