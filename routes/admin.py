"""
Admin Routes
=============
Full management dashboard for the Admin role.
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from models.user import User
from models.announcement import Announcement
from models.attendance import Attendance
from models.meeting_minutes import MeetingMinutes
from models.branch import Branch
from datetime import datetime, date
import json

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    total_members = User.query.filter_by(is_active=True).count()
    total_announcements = Announcement.query.count()
    total_meetings = MeetingMinutes.query.count()
    recent_announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all()
    recent_members = User.query.order_by(User.joined_date.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_members=total_members,
        total_announcements=total_announcements,
        total_meetings=total_meetings,
        recent_announcements=recent_announcements,
        recent_members=recent_members,
    )


# ── Members ───────────────────────────────────────────────────────────────────
@admin_bp.route("/members")
@login_required
@admin_required
def members():
    all_members = User.query.order_by(User.full_name).all()
    branches = Branch.query.all()
    return render_template("admin/members.html", members=all_members, branches=branches)


@admin_bp.route("/members/<int:uid>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_member(uid):
    user = User.query.get_or_404(uid)
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    flash(f"{user.full_name} has been {status}.", "success")
    return redirect(url_for("admin.members"))


@admin_bp.route("/members/<int:uid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_member(uid):
    user = User.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    flash("Member deleted.", "info")
    return redirect(url_for("admin.members"))

@admin_bp.route("/members/<int:uid>/edit", methods=["POST"])
@login_required
@admin_required
def edit_member(uid):
    user = User.query.get_or_404(uid)
    db.session.edit(user)
    db.session.commit()
    flash("Member edited.", "info")
    return redirect(url_for("admin.members"))




# ── Announcements ─────────────────────────────────────────────────────────────
@admin_bp.route("/announcements")
@login_required
@admin_required
def announcements():
    items = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("admin/announcements.html", announcements=items)


@admin_bp.route("/announcements/new", methods=["POST"])
@login_required
@admin_required
def new_announcement():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    is_pinned = request.form.get("is_pinned") == "on"
    audience = request.form.get("audience", "all")

    ann = Announcement(
        title=title, body=body,
        author_id=current_user.id,
        is_pinned=is_pinned, audience=audience,
    )
    db.session.add(ann)
    db.session.commit()
    flash("Announcement posted.", "success")
    return redirect(url_for("admin.announcements"))


@admin_bp.route("/announcements/<int:aid>/delete", methods=["POST"])
@login_required
@admin_required
def delete_announcement(aid):
    ann = Announcement.query.get_or_404(aid)
    db.session.delete(ann)
    db.session.commit()
    flash("Announcement deleted.", "info")
    return redirect(url_for("admin.announcements"))


# ── Attendance Analytics ──────────────────────────────────────────────────────
@admin_bp.route("/attendance")
@login_required
@admin_required
def attendance():
    records = (
        Attendance.query
        .join(User, Attendance.user_id == User.id)
        .order_by(Attendance.meeting_date.desc())
        .all()
    )
    return render_template("admin/attendance.html", records=records)


# ── Meeting Minutes ───────────────────────────────────────────────────────────
@admin_bp.route("/minutes")
@login_required
@admin_required
def minutes():
    all_minutes = MeetingMinutes.query.order_by(MeetingMinutes.meeting_date.desc()).all()
    return render_template("admin/minutes.html", minutes=all_minutes)


# ── Branches ──────────────────────────────────────────────────────────────────
@admin_bp.route("/branches", methods=["GET", "POST"])
@login_required
@admin_required
def branches():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        leader = request.form.get("leader_name", "").strip()
        b = Branch(name=name, location=location, leader_name=leader)
        db.session.add(b)
        db.session.commit()
        flash(f"Branch '{name}' created.", "success")
        return redirect(url_for("admin.branches"))

    all_branches = Branch.query.all()
    return render_template("admin/branches.html", branches=all_branches)
