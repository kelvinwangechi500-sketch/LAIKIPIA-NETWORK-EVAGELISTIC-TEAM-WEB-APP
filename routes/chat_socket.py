"""
WebSocket Events - Real-time chat using Flask-SocketIO
Handles: join room, send message, typing, read receipts, online status
"""
from flask import request
from flask_login import current_user
from flask_socketio import join_room, leave_room, emit
from extensions import db
from models.chat_message import ChatMessage, MessageRead
from models.user import User
from datetime import datetime

# Track online users: {user_id: socket_id}
online_users = {}

def register_socket_events(socketio):

    @socketio.on("connect")
    def on_connect():
        if current_user.is_authenticated:
            online_users[current_user.id] = request.sid
            # Update last seen
            current_user.last_seen = datetime.utcnow()
            db.session.commit()
            # Tell everyone this user is online
            emit("user_online", {
                "user_id": current_user.id,
                "name": current_user.full_name
            }, broadcast=True)

    @socketio.on("disconnect")
    def on_disconnect():
        if current_user.is_authenticated:
            online_users.pop(current_user.id, None)
            current_user.last_seen = datetime.utcnow()
            db.session.commit()
            emit("user_offline", {
                "user_id": current_user.id,
            }, broadcast=True)

    @socketio.on("join")
    def on_join(data):
        room = data.get("room")
        if room:
            join_room(room)
            # Send online users list to newly joined
            emit("online_users", {
                "users": list(online_users.keys())
            })

    @socketio.on("leave")
    def on_leave(data):
        room = data.get("room")
        if room:
            leave_room(room)

    @socketio.on("send_message")
    def on_send_message(data):
        if not current_user.is_authenticated:
            return
        room = data.get("room", "general")
        body = data.get("body", "").strip()
        client_id = data.get("client_id")
        reply_to_id = data.get("reply_to_id")

        if not body:
            return

        # Dedup
        if client_id and ChatMessage.query.filter_by(client_id=client_id).first():
            return

        reply_to = None
        if reply_to_id:
            reply_to = ChatMessage.query.get(reply_to_id)

        msg = ChatMessage(
            room=room,
            sender_id=current_user.id,
            body=body,
            msg_type="text",
            client_id=client_id,
            reply_to_id=reply_to_id,
        )
        db.session.add(msg)
        db.session.commit()

        msg_data = {
            "id": msg.id,
            "room": room,
            "body": body,
            "msg_type": "text",
            "file_url": None,
            "file_name": None,
            "file_size": None,
            "sender_id": current_user.id,
            "sender_name": current_user.full_name,
            "sender_avatar": current_user.full_name[0].upper(),
            "reply_to": {
                "id": reply_to.id,
                "body": reply_to.body[:60],
                "sender": reply_to.sender.full_name if reply_to and reply_to.sender else ""
            } if reply_to else None,
            "is_deleted": False,
            "read_count": 0,
            "time": msg.created_at.strftime("%H:%M"),
            "created_at": msg.created_at.isoformat(),
        }
        emit("new_message", msg_data, room=room)

    @socketio.on("typing")
    def on_typing(data):
        if not current_user.is_authenticated:
            return
        room = data.get("room")
        is_typing = data.get("typing", False)
        emit("typing", {
            "user_id": current_user.id,
            "name": current_user.full_name,
            "typing": is_typing,
        }, room=room, include_self=False)

    @socketio.on("mark_read")
    def on_mark_read(data):
        if not current_user.is_authenticated:
            return
        room = data.get("room")
        msg_id = data.get("msg_id")
        if msg_id:
            if not MessageRead.query.filter_by(message_id=msg_id, user_id=current_user.id).first():
                db.session.add(MessageRead(message_id=msg_id, user_id=current_user.id))
                db.session.commit()
            emit("message_read", {
                "msg_id": msg_id,
                "user_id": current_user.id,
                "room": room,
            }, room=room)

    @socketio.on("react")
    def on_react(data):
        if not current_user.is_authenticated:
            return
        emit("reaction", {
            "msg_id": data.get("msg_id"),
            "emoji": data.get("emoji"),
            "user_id": current_user.id,
            "name": current_user.full_name,
            "room": data.get("room"),
        }, room=data.get("room"))
