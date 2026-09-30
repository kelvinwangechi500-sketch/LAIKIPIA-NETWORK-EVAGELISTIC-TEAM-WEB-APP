"""
Member Routes
==============
Dashboard, announcements view, attendance history, chat, profile.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models.announcement import Announcement
from models.attendance import Attendance
from datetime import datetime

member_bp = Blueprint("member", __name__)


@member_bp.route("/dashboard")
@login_required
def dashboard():
    announcements = (
        Announcement.query
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(10).all()
    )
    my_attendance = (
        Attendance.query
        .filter_by(user_id=current_user.id)
        .order_by(Attendance.meeting_date.desc())
        .limit(10).all()
    )
    total = Attendance.query.filter_by(user_id=current_user.id).count()
    present = Attendance.query.filter_by(user_id=current_user.id, status="present").count()
    rate = round((present / total * 100) if total else 0, 1)

    return render_template(
        "member/dashboard.html",
        announcements=announcements,
        my_attendance=my_attendance,
        attendance_rate=rate,
        total_meetings=total,
        present_count=present,
    )


@member_bp.route("/attendance")
@login_required
def attendance():
    records = (
        Attendance.query
        .filter_by(user_id=current_user.id)
        .order_by(Attendance.meeting_date.desc())
        .all()
    )
    return render_template("member/attendance.html", records=records)


@member_bp.route("/chat")
@login_required
def chat():
    from flask import redirect, url_for
    return redirect(url_for('chat.index'))


@member_bp.route("/profile")
@login_required
def profile():
    return render_template("member/profile.html")
