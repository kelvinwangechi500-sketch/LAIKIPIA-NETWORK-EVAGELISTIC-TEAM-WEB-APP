from datetime import datetime
from extensions import db


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(120), nullable=False, default="general")
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    msg_type = db.Column(db.String(20), default="text")
    file_url = db.Column(db.String(500))
    file_name = db.Column(db.String(200))
    file_size = db.Column(db.Integer)
    client_id = db.Column(db.String(64), unique=True)
    reply_to_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"))
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reply_to = db.relationship("ChatMessage", remote_side=[id], lazy="joined")


class MessageRead(db.Model):
    __tablename__ = "message_reads"
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    read_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("message_id", "user_id"),)


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(150))
    room_type = db.Column(db.String(20), default="group")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
