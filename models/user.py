"""
User Model
===========
Roles: admin | vice_secretary | member
"""

from datetime import datetime
from flask_login import UserMixin
from extensions import db, login_manager


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="member")
    # role is one of: "admin", "vice_secretary", "member"

    phone = db.Column(db.String(20))
    residence = db.Column(db.String(150))
    year = db.Column(db.String(50))
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"))
    is_active = db.Column(db.Boolean, default=True)
    profile_pic = db.Column(db.String(300), default="")
    joined_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime)

    # Relationships — foreign_keys specified to avoid ambiguity
    attendance_records = db.relationship(
        "Attendance",
        foreign_keys="Attendance.user_id",
        backref="user",
        lazy="dynamic"
    )
    announcements = db.relationship(
        "Announcement",
        backref="author",
        lazy="dynamic"
    )
    chat_messages = db.relationship(
        "ChatMessage",
        backref="sender",
        lazy="dynamic"
    )

    def __repr__(self):
        return f"<User {self.email} [{self.role}]>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))